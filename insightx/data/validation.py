"""Fail-loud checks for observations and evaluation-only ground truth."""

import numpy as np
import pandas as pd

from insightx.data.anomalies import apply_event, event_mask, plan_events
from insightx.data.schema import (
    BUSINESS_COLUMNS, COUNT_COLUMNS, EVENT_COLUMNS, KEY_COLUMNS,
    LABEL_COLUMNS, NUMERIC_COLUMNS, PRODUCT_CATEGORIES, REGIONS, SEGMENTS,
)
from insightx.data.settings import GenerationConfig


def require(condition: bool, message: str) -> None:
    """Raise a validation error without relying on removable Python assertions."""
    if not condition:
        raise ValueError(message)


def validate_business(frame: pd.DataFrame, config: GenerationConfig) -> None:
    """Enforce the analytical allowlist, physical ranges, keys, and identities."""
    config.validate()
    require(list(frame.columns) == BUSINESS_COLUMNS,
            "Business schema mismatch or ground-truth leakage: only allowlisted columns are permitted.")
    require(not frame.empty, "Business data is empty.")
    require(not frame.isna().any().any(), "Business data contains nulls.")
    require(frame["record_id"].is_unique, "Duplicate record IDs.")
    require(frame["record_id"].astype(str).str.fullmatch(r"R[0-9]{7,}").all(),
            "Malformed record IDs.")
    require(not frame.duplicated(KEY_COLUMNS).any(), "Duplicate daily business keys.")
    parsed = pd.to_datetime(frame["date"], format="%Y-%m-%d", errors="coerce")
    require(parsed.notna().all(), "Invalid dates.")
    require(parsed.between(pd.Timestamp(config.start_date),
                           pd.Timestamp(config.end_date)).all(), "Dates outside configuration.")
    require(frame["product"].isin(PRODUCT_CATEGORIES).all(), "Unknown product.")
    require(frame["category"].eq(frame["product"].map(PRODUCT_CATEGORIES)).all(),
            "Inconsistent product/category mapping.")
    require(frame["region"].isin(REGIONS).all(), "Unknown region.")
    require(frame["customer_segment"].isin(SEGMENTS).all(), "Unknown customer segment.")
    for column in NUMERIC_COLUMNS:
        require(pd.api.types.is_numeric_dtype(frame[column]), f"{column} must be numeric.")
        require(np.isfinite(frame[column]).all(), f"{column} contains non-finite values.")
        require(frame[column].ge(0).all(), f"{column} must be non-negative.")
    for column in COUNT_COLUMNS:
        require(frame[column].eq(np.floor(frame[column])).all(), f"{column} must be integer.")
    require(frame["price"].gt(0).all(), "Prices must be positive.")
    require(frame["discount"].le(config.max_discount + 1e-10).all(), "Discount exceeds limit.")
    require(frame["returns"].le(frame["units"]).all(), "Returns exceed units.")
    active = frame["units"].gt(0)
    require(frame.loc[active, "orders"].gt(0).all(), "Active observations need positive orders.")
    require(frame["orders"].le(frame["units"]).all(), "Orders exceed units.")
    inactive = ~active
    require(frame.loc[inactive, ["orders", "returns", "revenue", "cost"]].eq(0).all().all(),
            "Zero-unit observations must have zero dependent totals.")
    expected_revenue = np.round(frame["units"] * frame["price"] * (1 - frame["discount"]), 2)
    require(np.allclose(frame["revenue"], expected_revenue, rtol=0, atol=0.005),
            "Revenue does not equal rounded units * price * (1 - discount).")
    require(frame.loc[active, "cost"].gt(0).all(), "Active observations need positive cost.")


def validate_ground_truth(
    observed: pd.DataFrame, baseline: pd.DataFrame, events: pd.DataFrame,
    labels: pd.DataFrame, config: GenerationConfig,
) -> None:
    """Check every changed record, event scope, label, and intervention formula."""
    validate_business(observed, config)
    validate_business(baseline, config)
    require(list(events.columns) == EVENT_COLUMNS, "Ground-truth event schema mismatch.")
    require(list(labels.columns) == LABEL_COLUMNS, "Label schema mismatch.")
    require(not events.isna().any().any() and not labels.isna().any().any(),
            "Ground truth contains nulls.")
    require(events["anomaly_id"].is_unique, "Duplicate anomaly IDs.")
    require(labels["record_id"].is_unique, "Duplicate label record IDs.")
    require(observed["record_id"].equals(baseline["record_id"])
            and observed["record_id"].equals(labels["record_id"]),
            "Record labels and baseline must align with observations.")
    unchanged_columns = [c for c in BUSINESS_COLUMNS if c not in NUMERIC_COLUMNS]
    require(observed[unchanged_columns].equals(baseline[unchanged_columns]),
            "Anomalies must not alter record IDs or business dimensions.")
    require(labels["is_anomaly"].isin([0, 1]).all(), "Labels must be 0 or 1.")
    planned = plan_events(config) if config.inject_anomalies else pd.DataFrame(columns=EVENT_COLUMNS)
    require(len(events) == len(planned), "Unexpected number of events.")
    fixed_fields = [c for c in EVENT_COLUMNS if c != "affected_records"]
    require(events[fixed_fields].reset_index(drop=True).equals(
        planned[fixed_fields].reset_index(drop=True)),
        "Event definitions differ from the configured synthetic interventions.")

    replay = baseline.copy(deep=True)
    expected_ids = pd.Series("normal", index=baseline.index)
    claimed = pd.Series(False, index=baseline.index)
    for event in events.to_dict("records"):
        mask = event_mask(baseline, event)
        require(not (mask & claimed).any(), "Overlapping anomaly windows/scopes.")
        claimed |= mask
        modified = apply_event(baseline, event, config)
        changed = modified[NUMERIC_COLUMNS].ne(baseline[NUMERIC_COLUMNS]).any(axis=1)
        require(changed.any(), f"Event {event['anomaly_id']} changes no data.")
        require(int(changed.sum()) == event["affected_records"], "Incorrect affected-record count.")
        require(not (changed & ~mask).any(), "Anomaly changed data outside its declared scope.")
        expected_ids.loc[changed] = event["anomaly_id"]
        replay.loc[changed, NUMERIC_COLUMNS] = modified.loc[changed, NUMERIC_COLUMNS]
    require(labels["anomaly_id"].eq(expected_ids).all(), "Incorrect event-to-record labels.")
    changed = observed[NUMERIC_COLUMNS].ne(baseline[NUMERIC_COLUMNS]).any(axis=1)
    require(changed.equals(labels["is_anomaly"].eq(1)), "Labels do not match actual changes.")
    require(np.allclose(observed[NUMERIC_COLUMNS], replay[NUMERIC_COLUMNS],
                        rtol=0, atol=1e-8), "Observed data does not match intervention replay.")


def validate_panel(frame: pd.DataFrame, config: GenerationConfig) -> None:
    """Verify coverage and the balanced-panel row count."""
    dates = pd.date_range(config.start_date, config.end_date)
    series_count = min(600, max(30, int(config.target_rows / len(dates) + 0.5)))
    require(len(frame) == series_count * len(dates), "Unexpected panel row count.")
    require(set(frame["date"]) == set(dates.strftime("%Y-%m-%d")), "Missing panel dates.")
    require(frame.groupby(["product", "region", "customer_segment"]).size().eq(len(dates)).all(),
            "Incomplete daily series.")
    require(set(frame["product"]) == set(PRODUCT_CATEGORIES), "Missing products.")
    require(set(frame["region"]) == set(REGIONS), "Missing regions.")
    require(set(frame["customer_segment"]) == set(SEGMENTS), "Missing customer segments.")
