"""Save and verify reproducible CSV bundles; evaluation files are never features."""

import hashlib
import json
import platform
import subprocess
from importlib.metadata import distributions
from pathlib import Path

import pandas as pd

from insightx.config import PROJECT_ROOT
from insightx.data import GENERATOR_VERSION
from insightx.data.anomalies import inject_anomalies
from insightx.data.generator import generate_baseline
from insightx.data.schema import ANOMALY_TYPES
from insightx.data.settings import GenerationConfig
from insightx.data.validation import require, validate_ground_truth, validate_panel

CSV_PATHS = {
    "business": "insightx_business_data.csv",
    "events": "insightx_ground_truth.csv",
    "labels": "evaluation/insightx_record_labels.csv",
    "baseline": "evaluation/insightx_baseline.csv",
}


def file_hash(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def source_identity() -> dict:
    """Record Git provenance honestly, including uncommitted generator changes."""
    source_files = sorted((PROJECT_ROOT / "insightx/data").glob("*.py"))
    source_files += [PROJECT_ROOT / "scripts/generate_dataset.py", PROJECT_ROOT / "requirements.txt"]
    digest = hashlib.sha256()
    for path in source_files:
        digest.update(path.relative_to(PROJECT_ROOT).as_posix().encode())
        digest.update(path.read_bytes())
    identity = {"source_sha256": digest.hexdigest(), "git_commit": "unavailable", "git_dirty": None}
    try:
        identity["git_commit"] = subprocess.check_output(
            ["git", "rev-parse", "HEAD"], cwd=PROJECT_ROOT, text=True, stderr=subprocess.DEVNULL,
        ).strip()
        identity["git_dirty"] = bool(subprocess.check_output(
            ["git", "status", "--porcelain"], cwd=PROJECT_ROOT, text=True, stderr=subprocess.DEVNULL,
        ).strip())
    except (OSError, subprocess.CalledProcessError):
        pass
    return identity


def write_bundle(
    output_dir: Path, observed: pd.DataFrame, events: pd.DataFrame,
    labels: pd.DataFrame, baseline: pd.DataFrame, config: GenerationConfig,
    overwrite: bool = False,
) -> dict:
    """Validate before saving. Require an explicit flag to replace existing outputs."""
    validate_ground_truth(observed, baseline, events, labels, config)
    validate_panel(observed, config)
    targets = [output_dir / name for name in CSV_PATHS.values()] + [output_dir / "metadata.json"]
    if not overwrite and any(path.exists() for path in targets):
        raise FileExistsError("Output bundle already exists; use another directory or --overwrite.")
    output_dir.mkdir(parents=True, exist_ok=True)
    frames = {"business": observed, "events": events, "labels": labels, "baseline": baseline}
    for key, relative_path in CSV_PATHS.items():
        path = output_dir / relative_path
        path.parent.mkdir(parents=True, exist_ok=True)
        frames[key].to_csv(path, index=False, lineterminator="\n", float_format="%.4f")
    metadata = {
        "generator_version": GENERATOR_VERSION, "config": config.to_dict(),
        "row_count": len(observed),
        "series_count": len(observed.drop_duplicates(["product", "region", "customer_segment"])),
        "python_version": platform.python_version(),
        "dependencies": dict(sorted((dist.metadata["Name"], dist.version) for dist in distributions())),
        "source": source_identity(),
        "sha256": {name: file_hash(output_dir / name) for name in CSV_PATHS.values()},
        "evaluation_only": [CSV_PATHS["events"], CSV_PATHS["labels"], CSV_PATHS["baseline"], "metadata.json"],
    }
    (output_dir / "metadata.json").write_text(
        json.dumps(metadata, indent=2, sort_keys=True) + "\n", encoding="utf-8",
    )
    return metadata


def validate_bundle(output_dir: Path) -> tuple[pd.DataFrame, pd.DataFrame, dict]:
    """Validate saved hashes, business rules, labels, and the reproducible baseline."""
    metadata = json.loads((output_dir / "metadata.json").read_text(encoding="utf-8"))
    require(metadata["generator_version"] == GENERATOR_VERSION, "Unsupported generator version.")
    config = GenerationConfig(**metadata["config"])
    for relative_path in CSV_PATHS.values():
        require(metadata["sha256"].get(relative_path) == file_hash(output_dir / relative_path),
                f"Checksum mismatch: {relative_path}")
    frames = {key: pd.read_csv(output_dir / path, keep_default_na=False)
              for key, path in CSV_PATHS.items()}
    validate_ground_truth(frames["business"], frames["baseline"],
                          frames["events"], frames["labels"], config)
    validate_panel(frames["business"], config)
    require(metadata["row_count"] == len(frames["business"]), "Metadata row count mismatch.")
    require(metadata["series_count"] == len(frames["business"].drop_duplicates(
        ["product", "region", "customer_segment"])), "Metadata series count mismatch.")
    expected = generate_baseline(config)
    try:
        pd.testing.assert_frame_equal(frames["baseline"], expected, check_dtype=False,
                                      check_exact=False, rtol=0, atol=1e-8)
    except AssertionError as exc:
        raise ValueError("Baseline replay differs; check configuration and dependency versions.") from exc
    return frames["business"], frames["events"], metadata


def generate_bundle(config: GenerationConfig, output_dir: Path, overwrite: bool = False) -> str:
    baseline = generate_baseline(config)
    observed, events, labels = inject_anomalies(baseline, config)
    write_bundle(output_dir, observed, events, labels, baseline, config, overwrite)
    return summary(observed, events)


def summary(observed: pd.DataFrame, events: pd.DataFrame) -> str:
    counts = events["anomaly_type"].value_counts()
    lines = [
        "InsightX synthetic dataset generated",
        f"Rows: {len(observed):,}",
        f"Date range: {observed['date'].min()} -> {observed['date'].max()}",
        f"Regions: {observed['region'].nunique()}",
        f"Products: {observed['product'].nunique()}",
        f"Categories: {observed['category'].nunique()}",
        f"Customer segments: {observed['customer_segment'].nunique()}",
        f"Injected anomaly events: {len(events)}",
    ]
    lines.extend(f"{kind}: {int(counts.get(kind, 0))}" for kind in ANOMALY_TYPES)
    lines.extend([
        f"Changed records: {int(events['affected_records'].sum())}",
        "Dataset validation: PASS", "Ground-truth validation: PASS",
    ])
    return "\n".join(lines)
