"""Explicit schemas separate observations from evaluation information."""

REGIONS = ("North", "South", "East", "West", "Central")
SEGMENTS = ("Consumer", "Corporate", "Small Business", "Enterprise")
CATEGORIES = ("Electronics", "Home", "Office", "Clothing", "Sports", "Personal Care")
PRODUCT_CATEGORIES = {
    f"P{i + 1:03d}": CATEGORIES[i % len(CATEGORIES)] for i in range(30)
}
BUSINESS_COLUMNS = [
    "record_id", "date", "region", "product", "category", "customer_segment",
    "units", "price", "discount", "revenue", "cost", "orders", "returns",
]
NUMERIC_COLUMNS = ["units", "price", "discount", "revenue", "cost", "orders", "returns"]
COUNT_COLUMNS = ["units", "orders", "returns"]
KEY_COLUMNS = ["date", "region", "product", "customer_segment"]
LABEL_COLUMNS = ["record_id", "is_anomaly", "anomaly_id"]
EVENT_COLUMNS = [
    "anomaly_id", "anomaly_type", "start_date", "end_date",
    "affected_region", "affected_product", "affected_category",
    "affected_metric", "manipulation", "true_contributing_factor",
    "severity", "parameter", "affected_records", "notes",
]
ANOMALY_TYPES = (
    "sales_decline", "regional_decline", "product_anomaly", "return_anomaly",
    "price_anomaly", "demand_spike", "seasonal_deviation",
)
