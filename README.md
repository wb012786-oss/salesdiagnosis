# 销售数据一键诊断 (Sales Diagnosis)

上传销售 Excel / CSV，自动生成经营诊断报告。

## 功能 v1.0

- 自动识别列：日期、金额、商品、数量、渠道、地区、客户、成本等（中英表头）
- 诊断摘要：销售额、笔数、客单价、日均、毛利（有成本时）
- 日销售趋势 + 环比
- 商品排行（占比、累计占比 / 帕累托）
- 渠道 / 地区汇总
- 客户集中度（Top5 / Top10）
- 异常：大额、负金额、日销环比大跌
- 规则化行动建议
- **隐私优先**：处理完即删，无账号、不落库

## 本地运行

```bash
python -m venv .venv
# Windows: .\.venv\Scripts\activate
source .venv/bin/activate
pip install -r requirements.txt
uvicorn app.main:app --host 127.0.0.1 --port 8000 --reload
```

打开 http://127.0.0.1:8000

## InstaBox

```bash
git clone <你的仓库> && cd sales-diagnosis
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
UPLOAD_DIR=/tmp/sales_uploads uvicorn app.main:app --host 0.0.0.0 --port 8000
```

发布 8000 端口即可。

## 样本

`samples/sample_sales.csv` 可直接上传测试。

## License

MIT
