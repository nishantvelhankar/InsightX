"""Controlled interventions; labels and generating factors stay outside features."""

import numpy as np
import pandas as pd

from insightx.data.generator import monthly_multiplier
from insightx.data.schema import ANOMALY_TYPES, EVENT_COLUMNS, NUMERIC_COLUMNS
from insightx.data.settings import GenerationConfig


def event_mask(frame: pd.DataFrame, event: dict) -> pd.Series:
    """Select the declared event window and scope, using inclusive dates."""
    mask = frame["date"].between(event["start_date"], event["end_date"])
    for column in ("region", "product", "category"):
        value = event[f"affected_{column}"]
        if value != "ALL":
            mask &= frame[column].eq(value)
    return mask


def plan_events(config: GenerationConfig) -> pd.DataFrame:
    """Place seven non-overlapping seven-day windows in the second half."""
    dates = pd.date_range(config.start_date, config.end_date)
    blocks = np.array_split(np.arange(len(dates) // 2, len(dates)), 7)
    specs = [
        ("units", 0.50, "units_multiplier", "temporary_demand_reduction"),
        ("units", 0.40, "units_multiplier", "regional_demand_reduction"),
        ("units", 0.35, "units_multiplier", "product_demand_reduction"),
        ("returns", 0.25, "add_unit_fraction_to_returns", "increased_return_propensity"),
        ("price", 1.60, "price_multiplier", "list_price_increase"),
        ("units", 2.20, "units_multiplier", "temporary_demand_increase"),
        ("units", 0.60, "remove_monthly_effect_then_scale", "suppressed_seasonal_demand"),
    ]
    events = []
    for i, (kind, block, spec) in enumerate(zip(ANOMALY_TYPES, blocks, specs)):
        if kind == "seasonal_deviation":
            # Choose the strongest normal seasonal week inside the final block.
            scores = np.convolve(
                monthly_multiplier(dates[block], config.seasonal_peaks),
                np.ones(7) / 7, mode="valid",
            )
            start_index = block[int(np.argmax(scores))]
        else:
            start_index = block[(len(block) - 7) // 2]
        metric, parameter, manipulation, factor = spec
        events.append({
            "anomaly_id": f"A{i + 1:03d}", "anomaly_type": kind,
            "start_date": dates[start_index].strftime("%Y-%m-%d"),
            "end_date": dates[start_index + 6].strftime("%Y-%m-%d"),
            "affected_region": "North" if kind == "regional_decline" else "ALL",
            "affected_product": "P001" if kind == "product_anomaly" else "ALL",
            "affected_category": (
                "Electronics" if kind == "return_anomaly"
                else "Home" if kind == "price_anomaly" else "ALL"
            ),
            "affected_metric": metric, "manipulation": manipulation,
            "true_contributing_factor": factor, "severity": "high",
            "parameter": parameter, "affected_records": 0,
            "notes": "Known synthetic intervention, not a real-world causal finding; no overlap.",
        })
    return pd.DataFrame(events, columns=EVENT_COLUMNS)


def apply_event(
    baseline: pd.DataFrame, event: dict, config: GenerationConfig,
) -> pd.DataFrame:
    """Apply a single event and recompute dependent values consistently."""
    result = baseline.copy(deep=True)
    mask = event_mask(baseline, event)
    part = baseline.loc[mask]
    kind = event["anomaly_type"]
    parameter = float(event["parameter"])
    if kind in {"sales_decline", "regional_decline", "product_anomaly",
                "demand_spike", "seasonal_deviation"}:
        scale = parameter
        if kind == "seasonal_deviation":
            scale = parameter / monthly_multiplier(
                pd.DatetimeIndex(part["date"]), config.seasonal_peaks,
            )
        units = np.maximum(1, np.floor(part["units"].to_numpy() * scale).astype(int))
        ratio = units / part["units"].to_numpy()
        result.loc[mask, "units"] = units
        result.loc[mask, "orders"] = np.clip(
            np.rint(part["orders"].to_numpy() * ratio).astype(int), 1, units,
        )
        result.loc[mask, "returns"] = np.clip(
            np.rint(part["returns"].to_numpy() * ratio).astype(int), 0, units,
        )
        # Keep this operation order fixed for reproducible cent rounding.
        result.loc[mask, "cost"] = np.round(
            part["cost"].to_numpy() * units / part["units"].to_numpy(), 2,
        )
    elif kind == "return_anomaly":
        result.loc[mask, "returns"] = np.minimum(
            part["units"],
            part["returns"] + np.ceil(part["units"] * parameter).astype(int),
        )
    elif kind == "price_anomaly":
        result.loc[mask, "price"] = np.round(part["price"] * parameter, 2)
    else:
        raise ValueError(f"Unsupported anomaly type: {kind}")
    result.loc[mask, "revenue"] = np.round(
        result.loc[mask, "units"] * result.loc[mask, "price"]
        * (1 - result.loc[mask, "discount"]), 2,
    )
    return result


def inject_anomalies(
    baseline: pd.DataFrame, config: GenerationConfig,
) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    """Return observations, event ground truth, and complete record-level labels."""
    observed = baseline.copy(deep=True)
    labels = pd.DataFrame({
        "record_id": baseline["record_id"], "is_anomaly": 0, "anomaly_id": "normal",
    })
    events = (
        plan_events(config) if config.inject_anomalies
        else pd.DataFrame(columns=EVENT_COLUMNS)
    )
    claimed = pd.Series(False, index=baseline.index)
    for index, event in events.iterrows():
        mask = event_mask(baseline, event)
        if (claimed & mask).any():
            raise ValueError("Overlapping event scopes are not supported in Phase 2.")
        claimed |= mask
        modified = apply_event(baseline, event.to_dict(), config)
        changed = modified[NUMERIC_COLUMNS].ne(baseline[NUMERIC_COLUMNS]).any(axis=1)
        if not changed.any():
            raise ValueError(f"Event {event['anomaly_id']} changed no records.")
        observed.loc[changed, NUMERIC_COLUMNS] = modified.loc[changed, NUMERIC_COLUMNS]
        labels.loc[changed, "is_anomaly"] = 1
        labels.loc[changed, "anomaly_id"] = event["anomaly_id"]
        events.loc[index, "affected_records"] = int(changed.sum())
    return observed, events, labels
