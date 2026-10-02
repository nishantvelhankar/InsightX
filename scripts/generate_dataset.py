"""CLI entry point: python scripts/generate_dataset.py --help."""

import argparse
import sys
from pathlib import Path

# Direct script execution puts scripts/, not the repository root, on sys.path.
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from insightx.config import PROJECT_ROOT
from insightx.data.io import generate_bundle, summary, validate_bundle
from insightx.data.settings import GenerationConfig


def main() -> int:
    parser = argparse.ArgumentParser(description="Generate or validate InsightX synthetic research data.")
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--start-date", default="2024-01-01")
    parser.add_argument("--end-date", default="2025-12-31")
    parser.add_argument("--rows", type=int, default=100_000, help="Approximate target; balanced daily panel.")
    parser.add_argument("--no-anomalies", action="store_true")
    parser.add_argument("--no-seasonal-peaks", action="store_true")
    parser.add_argument("--max-discount", type=float, default=0.40)
    parser.add_argument("--output-dir", type=Path, default=PROJECT_ROOT / "data/synthetic")
    parser.add_argument("--overwrite", action="store_true", help="Replace an existing generated bundle.")
    parser.add_argument("--validate-only", action="store_true",
                        help="Read configuration from saved metadata and validate the saved bundle.")
    args = parser.parse_args()
    try:
        if args.validate_only:
            observed, events, _ = validate_bundle(args.output_dir)
            print("Saved bundle checksums and baseline replay: PASS")
            print(summary(observed, events).replace("generated", "validated", 1))
        else:
            config = GenerationConfig(
                seed=args.seed, start_date=args.start_date, end_date=args.end_date,
                target_rows=args.rows, inject_anomalies=not args.no_anomalies,
                seasonal_peaks=not args.no_seasonal_peaks, max_discount=args.max_discount,
            )
            print(generate_bundle(config, args.output_dir, args.overwrite))
        print(f"Output directory: {args.output_dir.resolve()}")
    except (ValueError, OSError, KeyError, TypeError) as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
