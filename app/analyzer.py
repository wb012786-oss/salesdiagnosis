"""
销售数据解析与诊断分析
自动识别列 → 标准化 → 汇总 / 排行 / 异常 / 简单建议
"""
from __future__ import annotations

import re
from datetime import datetime
from pathlib import Path
from typing import Any

import pandas as pd
from dateutil import parser as date_parser

from .config import COLUMN_ALIASES


def _norm_col(name: str) -> str:
    return re.sub(r"\s+", "", str(name).strip().lower())


def detect_columns(df: pd.DataFrame) -> dict[str, str | None]:
    """根据表头关键词映射到标准字段，返回 {标准名: 原列名}"""
    mapping: dict[str, str | None] = {k: None for k in COLUMN_ALIASES}
    used = set()
    cols = list(df.columns)

    for std, aliases in COLUMN_ALIASES.items():
        for col in cols:
            if col in used:
                continue
            n = _norm_col(col)
            for a in aliases:
                if _norm_col(a) in n or n in _norm_col(a) or n == _norm_col(a):
                    mapping[std] = col
                    used.add(col)
                    break
            if mapping[std]:
                break
    return mapping


def parse_date(val: Any) -> pd.Timestamp | pd.NaT:
    if val is None or (isinstance(val, float) and pd.isna(val)):
        return pd.NaT
    if isinstance(val, (pd.Timestamp, datetime)):
        return pd.Timestamp(val)
    s = str(val).strip()
    if not s:
        return pd.NaT
    for fmt in ("%Y-%m-%d", "%Y/%m/%d", "%Y.%m.%d", "%Y%m%d", "%Y-%m-%d %H:%M:%S", "%Y/%m/%d %H:%M"):
        try:
            return pd.Timestamp(datetime.strptime(s[:19], fmt))
        except ValueError:
            continue
    try:
        return pd.Timestamp(date_parser.parse(s, fuzzy=True))
    except Exception:
        return pd.NaT


def clean_number(val: Any) -> float | None:
    if val is None or (isinstance(val, float) and pd.isna(val)):
        return None
    s = str(val).strip().replace(",", "").replace("，", "").replace("¥", "").replace("￥", "").replace("%", "")
    s = re.sub(r"[^\d.\-]", "", s)
    if not s or s in ("-", "."):
        return None
    try:
        return float(s)
    except ValueError:
        return None


def load_file(path: Path) -> tuple[pd.DataFrame, list[str]]:
    warnings: list[str] = []
    suffix = path.suffix.lower()
    try:
        if suffix == ".csv":
            for enc in ("utf-8-sig", "utf-8", "gbk", "gb2312"):
                try:
                    df = pd.read_csv(path, encoding=enc, dtype=str)
                    break
                except UnicodeDecodeError:
                    continue
            else:
                raise ValueError("无法识别 CSV 编码")
        else:
            df = pd.read_excel(path, dtype=str)
    except Exception as e:
        raise ValueError(f"读取文件失败: {e}") from e

    if df.empty or len(df.columns) < 1:
        raise ValueError("文件无有效数据")

    # 去掉全空行
    df = df.dropna(how="all").reset_index(drop=True)
    return df, warnings


def standardize(df: pd.DataFrame) -> tuple[pd.DataFrame, dict, list[str]]:
    """返回标准化表、列映射、警告"""
    warnings: list[str] = []
    mapping = detect_columns(df)

    if not mapping.get("amount"):
        # 尝试找数值最多的列当金额
        for col in df.columns:
            sample = df[col].head(50).apply(clean_number)
            if sample.notna().sum() >= max(3, len(sample) // 3):
                mapping["amount"] = col
                warnings.append(f"未识别到明确金额列，已猜测使用「{col}」")
                break

    if not mapping.get("amount"):
        raise ValueError("无法识别销售额/金额列，请保证表头含「金额」「销售额」「实付」等字样")

    out = pd.DataFrame()
    out["金额"] = df[mapping["amount"]].apply(clean_number)

    if mapping.get("date"):
        out["日期"] = df[mapping["date"]].apply(parse_date)
    else:
        out["日期"] = pd.NaT
        warnings.append("未识别到日期列，趋势与同比分析将跳过")

    if mapping.get("qty"):
        out["数量"] = df[mapping["qty"]].apply(clean_number)
    else:
        out["数量"] = None

    for std, label in [
        ("product", "商品"),
        ("sku", "SKU"),
        ("region", "地区"),
        ("channel", "渠道"),
        ("customer", "客户"),
        ("order_id", "订单号"),
    ]:
        if mapping.get(std):
            out[label] = df[mapping[std]].astype(str).str.strip()
        else:
            out[label] = None

    if mapping.get("cost"):
        out["成本"] = df[mapping["cost"]].apply(clean_number)
    else:
        out["成本"] = None

    # 过滤无金额行
    before = len(out)
    out = out[out["金额"].notna()].copy()
    if len(out) < before:
        warnings.append(f"已忽略 {before - len(out)} 行无效金额")

    if out.empty:
        raise ValueError("没有有效的金额数据")

    return out, mapping, warnings


def diagnose(df: pd.DataFrame) -> dict:
    """核心诊断逻辑，返回各块结果"""
    result: dict[str, Any] = {}

    # —— 总览 ——
    total_sales = float(df["金额"].sum())
    order_count = len(df)
    aov = total_sales / order_count if order_count else 0
    qty_sum = df["数量"].sum() if df["数量"].notna().any() else None

    overview = {
        "有效行数": order_count,
        "销售总额": round(total_sales, 2),
        "客单价/笔均": round(aov, 2),
        "销售数量合计": round(float(qty_sum), 2) if qty_sum is not None and pd.notna(qty_sum) else "—",
    }

    if df["日期"].notna().any():
        dmin, dmax = df["日期"].min(), df["日期"].max()
        overview["日期范围"] = f"{dmin.strftime('%Y-%m-%d')} ~ {dmax.strftime('%Y-%m-%d')}"
        days = max((dmax - dmin).days + 1, 1)
        overview["日均销售额"] = round(total_sales / days, 2)
    else:
        overview["日期范围"] = "未知"
        overview["日均销售额"] = "—"

    if df["成本"].notna().any():
        total_cost = float(df["成本"].sum())
        overview["成本合计"] = round(total_cost, 2)
        overview["毛利估算"] = round(total_sales - total_cost, 2)
        overview["毛利率"] = f"{((total_sales - total_cost) / total_sales * 100):.1f}%" if total_sales else "—"

    result["overview"] = overview

    # —— 按日趋势 ——
    trend = pd.DataFrame()
    if df["日期"].notna().any():
        tmp = df.dropna(subset=["日期"]).copy()
        tmp["日"] = tmp["日期"].dt.date
        trend = (
            tmp.groupby("日", as_index=False)
            .agg(销售额=("金额", "sum"), 笔数=("金额", "count"))
            .sort_values("日")
        )
        trend["日"] = trend["日"].astype(str)
        if len(trend) >= 2:
            trend["环比额"] = trend["销售额"].pct_change()
    result["trend"] = trend

    # —— 商品排行 ——
    product_rank = pd.DataFrame()
    if df["商品"].notna().any() and (df["商品"] != "None").any() and (df["商品"] != "").any():
        g = df[df["商品"].notna() & (df["商品"] != "") & (df["商品"] != "None")]
        product_rank = (
            g.groupby("商品", as_index=False)
            .agg(销售额=("金额", "sum"), 笔数=("金额", "count"), 数量=("数量", "sum"))
            .sort_values("销售额", ascending=False)
        )
        product_rank["占比%"] = (product_rank["销售额"] / total_sales * 100).round(2)
        product_rank["累计占比%"] = product_rank["占比%"].cumsum().round(2)
    result["product_rank"] = product_rank

    # —— 渠道 / 地区 ——
    channel_rank = pd.DataFrame()
    if df["渠道"].notna().any() and (df["渠道"] != "None").any():
        g = df[df["渠道"].notna() & (df["渠道"] != "") & (df["渠道"] != "None")]
        channel_rank = (
            g.groupby("渠道", as_index=False)
            .agg(销售额=("金额", "sum"), 笔数=("金额", "count"))
            .sort_values("销售额", ascending=False)
        )
        channel_rank["占比%"] = (channel_rank["销售额"] / total_sales * 100).round(2)
    result["channel_rank"] = channel_rank

    region_rank = pd.DataFrame()
    if df["地区"].notna().any() and (df["地区"] != "None").any():
        g = df[df["地区"].notna() & (df["地区"] != "") & (df["地区"] != "None")]
        region_rank = (
            g.groupby("地区", as_index=False)
            .agg(销售额=("金额", "sum"), 笔数=("金额", "count"))
            .sort_values("销售额", ascending=False)
            .head(30)
        )
        region_rank["占比%"] = (region_rank["销售额"] / total_sales * 100).round(2)
    result["region_rank"] = region_rank

    # —— 客户集中度 ——
    customer_stats = {}
    if df["客户"].notna().any() and (df["客户"] != "None").any():
        g = df[df["客户"].notna() & (df["客户"] != "") & (df["客户"] != "None")]
        cust = g.groupby("客户")["金额"].sum().sort_values(ascending=False)
        top5 = float(cust.head(5).sum())
        top10 = float(cust.head(10).sum())
        customer_stats = {
            "客户数": int(cust.shape[0]),
            "Top5客户销售额占比%": round(top5 / total_sales * 100, 2) if total_sales else 0,
            "Top10客户销售额占比%": round(top10 / total_sales * 100, 2) if total_sales else 0,
        }
    result["customer_stats"] = customer_stats

    # —— 异常检测 ——
    anomalies = []
    amounts = df["金额"]
    if len(amounts) >= 5:
        mean, std = amounts.mean(), amounts.std()
        if std and std > 0:
            high = mean + 3 * std
            for _, row in df[amounts > high].iterrows():
                anomalies.append({
                    "类型": "异常大额",
                    "日期": str(row["日期"].date()) if pd.notna(row["日期"]) else "",
                    "商品": row.get("商品") or "",
                    "金额": row["金额"],
                    "说明": f"超过均值+3倍标准差({high:.0f})",
                })
        # 负金额
        for _, row in df[amounts < 0].iterrows():
            anomalies.append({
                "类型": "负金额",
                "日期": str(row["日期"].date()) if pd.notna(row["日期"]) else "",
                "商品": row.get("商品") or "",
                "金额": row["金额"],
                "说明": "可能是退款或录入错误",
            })

    # 日销售额暴跌（环比 < -50% 且前一日有量）
    if not trend.empty and "环比额" in trend.columns:
        for _, row in trend.iterrows():
            r = row.get("环比额")
            if pd.notna(r) and r < -0.5 and row["销售额"] > 0:
                anomalies.append({
                    "类型": "日销环比大跌",
                    "日期": row["日"],
                    "商品": "",
                    "金额": row["销售额"],
                    "说明": f"环比 {r*100:.0f}%",
                })

    result["anomalies"] = pd.DataFrame(anomalies) if anomalies else pd.DataFrame(
        columns=["类型", "日期", "商品", "金额", "说明"]
    )

    # —— 简单建议（规则） ——
    tips = []
    if not product_rank.empty and len(product_rank) >= 3:
        top_share = float(product_rank.head(3)["占比%"].sum())
        if top_share >= 60:
            tips.append(f"头部 3 个商品贡献约 {top_share:.0f}% 销售额，结构偏集中，可关注供应与备货风险。")
        # 帕累托：累计达到 80% 的商品个数
        over80 = product_rank[product_rank["累计占比%"] >= 80]
        if not over80.empty:
            n80 = int(over80.index[0]) + 1
            n80 = max(1, min(n80, len(product_rank)))
            tips.append(f"约前 {n80} 个商品贡献了约 80% 销售额（帕累托），可优先保障这些 SKU。")

    if customer_stats.get("Top5客户销售额占比%", 0) >= 40:
        tips.append(
            f"Top5 客户占比约 {customer_stats['Top5客户销售额占比%']}%，客户较集中，建议拓展新客降低依赖。"
        )

    if not channel_rank.empty and len(channel_rank) >= 2:
        top_ch = channel_rank.iloc[0]
        tips.append(f"主渠道「{top_ch['渠道']}」占比 {top_ch['占比%']}%，可对比其他渠道投放效率。")

    if df["金额"].lt(0).any():
        tips.append("存在负金额记录，请核对是否为退款未单独标注，避免和正销售混算。")

    if not tips:
        tips.append("数据量或维度有限，建议补充「日期、商品、渠道、地区」列后再诊断，结论会更完整。")

    result["tips"] = tips
    return result


def run_diagnosis(path: Path, original_name: str = "") -> tuple[pd.DataFrame, dict, list[str]]:
    raw, w1 = load_file(path)
    std, mapping, w2 = standardize(raw)
    report = diagnose(std)
    report["column_mapping"] = mapping
    report["filename"] = original_name or path.name
    warnings = w1 + w2
    return std, report, warnings
