import os
import tempfile
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent

_default_upload = Path(tempfile.gettempdir()) / "sales_diagnosis_uploads"
UPLOAD_DIR = Path(os.getenv("UPLOAD_DIR", str(_default_upload)))
UPLOAD_DIR.mkdir(parents=True, exist_ok=True)

MAX_FILE_SIZE_MB = int(os.getenv("MAX_FILE_SIZE_MB", "20"))
MAX_FILE_SIZE = MAX_FILE_SIZE_MB * 1024 * 1024
MAX_FILES = int(os.getenv("MAX_FILES", "3"))

ALLOWED_EXTENSIONS = {".xlsx", ".xls", ".csv"}

# 列名映射关键词（中英）
COLUMN_ALIASES = {
    "date": ["日期", "订单日期", "成交日期", "时间", "date", "order_date", "成交时间", "下单时间", "交易日期"],
    "amount": ["金额", "销售额", "成交额", "实付", "收款", "amount", "sales", "revenue", "实付金额", "支付金额", "订单金额", "总金额"],
    "qty": ["数量", "销量", "件数", "qty", "quantity", "销售数量", "商品数量"],
    "product": ["商品", "产品", "品名", "商品名称", "product", "item", "sku名称", "货品", "标题"],
    "sku": ["sku", "货号", "编码", "商品编码", "product_id", "sku编码"],
    "region": ["地区", "省份", "城市", "区域", "region", "province", "收货省份", "收货城市", "省", "市"],
    "channel": ["渠道", "平台", "来源", "店铺", "channel", "platform", "store", "销售渠道", "订单来源"],
    "customer": ["客户", "买家", "用户", "customer", "buyer", "买家昵称", "客户名称", "会员"],
    "cost": ["成本", "cost", "进货价", "成本价"],
    "order_id": ["订单号", "订单编号", "order_id", "order_no", "交易号"],
}