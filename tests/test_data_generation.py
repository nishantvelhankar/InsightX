"""Research dataset contracts, interventions, reproducibility, and rejection tests."""

from dataclasses import replace
from pathlib import Path
import subprocess
import sys

import numpy as np
import pandas as pd
import pytest

from insightx.data.anomalies import event_mask, inject_anomalies
from insightx.data.generator import generate_baseline, monthly_multiplier
from insightx.data.io import CSV_PATHS, generate_bundle, validate_bundle, write_bundle
from insightx.data.schema import (
    ANOMALY_TYPES, BUSINESS_COLUMNS, EVENT_COLUMNS, LABEL_COLUMNS,
    NUMERIC_COLUMNS, PRODUCT_CATEGORIES,
)
from insightx.data.settings import GenerationConfig
from insightx.data.validation import validate_business, validate_ground_truth, validate_panel


@pytest.fixture(scope="module")
def config():
    return GenerationConfig(start_date="2025-01-01", end_date="2025-04-30", target_rows=5000)


@pytest.fixture(scope="module")
def bundle(config):
    baseline = generate_baseline(config)
    observed, events, labels = inject_anomalies(baseline, config)
    return baseline, observed, events, labels


def test_deterministic_generation(config, bundle):
    first_baseline, *first_outputs = bundle
    second_baseline = generate_baseline(config)
    pd.testing.assert_frame_equal(first_baseline, second_baseline)
    for first, second in zip(first_outputs, inject_anomalies(second_baseline, config)):
        pd.testing.assert_frame_equal(first, second)


def test_different_seed_changes_values(config, bundle):
    alternative = generate_baseline(replace(config, seed=43))
    assert not bundle[0].equals(alternative)


def test_business_schema_ids_ranges_and_balanced_panel(config, bundle):
    baseline, observed, _, _ = bundle
    assert list(observed.columns) == BUSINESS_COLUMNS
    assert observed["record_id"].is_unique
    assert len(observed) == 5040
    assert observed["date"].nunique() == 120
    assert observed["product"].nunique() == 30
    assert observed["region"].nunique() == 5
    assert observed["customer_segment"].nunique() == 4
    for frame in (baseline, observed):
        validate_business(frame, config)
        validate_panel(frame, config)
        assert frame["orders"].between(1, frame["units"]).all()
        assert frame["returns"].between(0, frame["units"]).all()


def test_product_category_consistency(bundle):
    for frame in bundle[:2]:
        assert frame["category"].equals(frame["product"].map(PRODUCT_CATEGORIES))


def test_ground_truth_and_unchanged_controls(config, bundle):
    baseline, observed, events, labels = bundle
    assert list(events.columns) == EVENT_COLUMNS
    assert list(labels.columns) == LABEL_COLUMNS
    assert set(events["anomaly_type"]) == set(ANOMALY_TYPES)
    validate_ground_truth(observed, baseline, events, labels, config)
    controls = labels["is_anomaly"].eq(0)
    pd.testing.assert_frame_equal(observed.loc[controls], baseline.loc[controls])
    assert labels["is_anomaly"].sum() == events["affected_records"].sum()
    assert events["affected_records"].gt(0).all()
    assert not baseline.equals(observed)


@pytest.mark.parametrize("kind", ANOMALY_TYPES)
def test_independent_intervention_arithmetic(kind, config, bundle):
    baseline, observed, events, labels = bundle
    event = events.loc[events["anomaly_type"].eq(kind)].iloc[0]
    mask = event_mask(baseline, event.to_dict())
    before, after = baseline.loc[mask], observed.loc[mask]
    parameter = event["parameter"]
    if kind == "return_anomaly":
        expected = np.minimum(before["units"], before["returns"]
                              + np.ceil(before["units"] * 0.25).astype(int))
        np.testing.assert_array_equal(after["returns"], expected)
        pd.testing.assert_frame_equal(
            before.drop(columns="returns"), after.drop(columns="returns"),
        )
    elif kind == "price_anomaly":
        np.testing.assert_array_equal(after["price"], np.round(before["price"] * 1.60, 2))
        pd.testing.assert_frame_equal(before[["units", "cost", "returns", "orders"]],
                                      after[["units", "cost", "returns", "orders"]])
    else:
        expected_scale = parameter
        if kind == "seasonal_deviation":
            expected_scale = 0.60 / monthly_multiplier(
                pd.DatetimeIndex(before["date"]), config.seasonal_peaks,
            )
        expected_units = np.maximum(1, np.floor(before["units"] * expected_scale).astype(int))
        np.testing.assert_array_equal(after["units"], expected_units)
        np.testing.assert_allclose(
            after["cost"], np.round(before["cost"] * expected_units / before["units"], 2),
            rtol=0, atol=0.005,
        )
        if kind == "demand_spike":
            assert (after["units"] > before["units"]).all()
        else:
            assert (after["units"] < before["units"]).all()
    np.testing.assert_allclose(
        after["revenue"], np.round(after["units"] * after["price"] * (1 - after["discount"]), 2),
        rtol=0, atol=0.005,
    )
    assert labels.loc[mask, "anomaly_id"].eq(event["anomaly_id"]).all()


def test_no_overlapping_events(bundle):
    baseline, _, events, _ = bundle
    membership = np.zeros(len(baseline), dtype=int)
    for event in events.to_dict("records"):
        membership += event_mask(baseline, event).to_numpy()
    assert membership.max() == 1
    ordered = events.sort_values("start_date")
    assert all(a < b for a, b in zip(ordered["end_date"][:-1], ordered["start_date"][1:]))


@pytest.mark.parametrize("leaked_column", [
    "is_anomaly", "anomaly_type", "anomaly_id", "true_contributing_factor",
    "expected_units", "baseline_revenue", "hidden_cause",
])
def test_ground_truth_leakage_rejected(leaked_column, config, bundle):
    contaminated = bundle[1].assign(**{leaked_column: "not_a_feature"})
    with pytest.raises(ValueError, match="schema mismatch or ground-truth leakage"):
        validate_business(contaminated, config)


def test_without_anomalies(config):
    config = replace(config, inject_anomalies=False)
    baseline = generate_baseline(config)
    observed, events, labels = inject_anomalies(baseline, config)
    pd.testing.assert_frame_equal(baseline, observed)
    assert events.empty and list(events.columns) == EVENT_COLUMNS
    assert labels["is_anomaly"].eq(0).all()
    assert labels["anomaly_id"].eq("normal").all()
    validate_ground_truth(observed, baseline, events, labels, config)


@pytest.mark.parametrize("anomalies", [True, False])
def test_output_round_trip_and_csv_reproducibility(config, tmp_path, anomalies):
    config = replace(config, inject_anomalies=anomalies)
    first, second = tmp_path / "first", tmp_path / "second"
    generate_bundle(config, first)
    generate_bundle(config, second)
    loaded, events, metadata = validate_bundle(first)
    assert len(loaded) == metadata["row_count"]
    assert len(events) == (7 if anomalies else 0)
    for name in CSV_PATHS.values():
        assert (first / name).read_bytes() == (second / name).read_bytes()
    with pytest.raises(FileExistsError):
        generate_bundle(config, first)
    generate_bundle(config, first, overwrite=True)
    validate_bundle(first)


@pytest.mark.parametrize(("column", "value"), [
    ("price", 0), ("units", -1), ("units", 1.5), ("revenue", -1),
    ("revenue", 0), ("cost", -1), ("cost", np.inf), ("returns", -1),
    ("returns", 999999), ("orders", 0), ("orders", 999999), ("discount", 0.9),
    ("price", np.nan), ("date", "not-a-date"), ("date", "2030-01-01"),
    ("category", "wrong"), ("region", "unknown"), ("customer_segment", "unknown"),
    ("product", "unknown"),
])
def test_invalid_business_data_rejected(column, value, config, bundle):
    broken = bundle[1].copy()
    if column in ("units", "cost") and isinstance(value, float):
        broken[column] = broken[column].astype(float)
    broken.loc[0, column] = value
    with pytest.raises(ValueError):
        validate_business(broken, config)


def test_duplicate_ids_and_missing_columns_rejected(config, bundle):
    broken = bundle[1].copy()
    broken.loc[1, "record_id"] = broken.loc[0, "record_id"]
    with pytest.raises(ValueError, match="Duplicate record IDs"):
        validate_business(broken, config)
    with pytest.raises(ValueError, match="schema mismatch"):
        validate_business(bundle[1].drop(columns="price"), config)


def test_false_labels_and_false_causes_rejected(config, bundle):
    baseline, observed, events, labels = bundle
    false_labels = labels.copy()
    false_labels.loc[0, "is_anomaly"] = 1
    with pytest.raises(ValueError):
        validate_ground_truth(observed, baseline, events, false_labels, config)
    false_events = events.copy()
    false_events.loc[0, "true_contributing_factor"] = "invented_cause"
    with pytest.raises(ValueError, match="Event definitions"):
        validate_ground_truth(observed, baseline, false_events, labels, config)


def test_wrong_counts_and_unexplained_numeric_changes_rejected(config, bundle):
    baseline, observed, events, labels = bundle
    false_events = events.copy()
    false_events.loc[0, "affected_records"] += 1
    with pytest.raises(ValueError, match="affected-record count"):
        validate_ground_truth(observed, baseline, false_events, labels, config)
    changed = observed.copy()
    changed.loc[0, "cost"] += 1
    with pytest.raises(ValueError, match="actual changes"):
        validate_ground_truth(changed, baseline, events, labels, config)


def test_corrupted_saved_file_rejected(config, tmp_path):
    generate_bundle(config, tmp_path)
    path = tmp_path / CSV_PATHS["business"]
    path.write_text(path.read_text() + "\n", encoding="utf-8")
    with pytest.raises(ValueError, match="Checksum mismatch"):
        validate_bundle(tmp_path)


@pytest.mark.parametrize("changes", [
    {"seed": -1}, {"target_rows": 0}, {"target_rows": 1_000_000},
    {"start_date": "bad"}, {"end_date": "2020-01-01"},
    {"end_date": "2025-01-15"}, {"max_discount": 0.9},
])
def test_invalid_config_rejected(config, changes):
    with pytest.raises(ValueError):
        generate_baseline(replace(config, **changes))


def test_short_clean_dataset_and_disabled_peaks():
    config = GenerationConfig(
        start_date="2025-12-01", end_date="2025-12-05", target_rows=150,
        inject_anomalies=False, seasonal_peaks=False,
    )
    baseline = generate_baseline(config)
    assert len(baseline) == 150
    validate_business(baseline, config)
    dates = pd.date_range("2025-11-01", "2025-12-31")
    assert (monthly_multiplier(dates, True) > monthly_multiplier(dates, False)).all()


def test_cli_runs_from_another_working_directory(tmp_path):
    script = Path(__file__).resolve().parents[1] / "scripts/generate_dataset.py"
    result = subprocess.run([
        sys.executable, str(script), "--rows", "150", "--start-date", "2025-12-01",
        "--end-date", "2025-12-05", "--no-anomalies", "--output-dir", str(tmp_path / "out"),
    ], cwd=tmp_path, text=True, capture_output=True)
    assert result.returncode == 0, result.stderr
    assert "Dataset validation: PASS" in result.stdout
    validation = subprocess.run([
        sys.executable, str(script), "--validate-only", "--output-dir", str(tmp_path / "out"),
    ], cwd=tmp_path, text=True, capture_output=True)
    assert validation.returncode == 0, validation.stderr


@pytest.mark.parametrize("cap", [0, 0.00008, 0.6])
def test_discount_cap_survives_serialization(config, tmp_path, cap):
    config = replace(config, max_discount=cap, inject_anomalies=False)
    generate_bundle(config, tmp_path)
    observed, _, _ = validate_bundle(tmp_path)
    assert observed["discount"].between(0, cap).all()
