# InsightX

**An Evidence-Guided Agentic Framework for Reliable GenAI-Based Investigation of Anomalies in Structured Data**

Current implementation: **Phase 2 — synthetic research dataset and controlled ground truth**.

Phase 1 provides settings, a health check, and environment tests. Phase 2 adds reproducible normal business data, seven controlled interventions, evaluation-only labels and baseline, saved-file validation, and tests. ML, data-analysis tools, GenAI, agents, API, database, and dashboard are not implemented.

## Setup

Use Python **3.12.x** and Git. In an existing clean checkout, run:

```bash
git pull --ff-only origin main
```

For a new checkout:

```bash
git clone https://github.com/nishantvelhankar/InsightX.git
cd InsightX
```

Windows Command Prompt (skip environment creation if your Python 3.12 venv exists):

```bat
py -3.12 -m venv .venv
.venv\Scripts\activate.bat
python -m pip install -r requirements.txt
if not exist .env copy .env.example .env
python --version
python -m pip check
python -m insightx.health
```

PowerShell activation is `.\.venv\Scripts\Activate.ps1`. If script execution is blocked, use Command Prompt or invoke `.\.venv\Scripts\python.exe` directly.

macOS/Linux:

```bash
python3.12 -m venv .venv
source .venv/bin/activate
python -m pip install -r requirements.txt
test -f .env || cp .env.example .env
python --version
python -m pip check
python -m insightx.health
```

Phase 2 adds only NumPy **2.2.6** and Pandas **2.2.3** as direct dependencies. Pip installs their required dependencies. The original python-dotenv 1.1.0 and Pytest 8.3.5 pins remain. No API key or database is required.

## Generate, validate, and test

Run from the repository root with the environment active:

```bash
python scripts/generate_dataset.py
python scripts/generate_dataset.py --validate-only
python -m pytest -q
```

For intentional regeneration:

```bash
python scripts/generate_dataset.py --overwrite
```

The default produces **100,147 rows**: 137 fixed daily product-region-segment series x 731 dates, covering 2024-01-01 to 2025-12-31. There are 5 regions, 30 products, 6 categories, 4 segments, seven isolated events, and **3,395 changed records**. The script computes these counts.

## Generated files

Paths below are relative to project-root `data/synthetic/` by default.

| File | Purpose | Future analysis input? |
| --- | --- | --- |
| insightx_business_data.csv | Observable business values | Yes; only this file |
| insightx_ground_truth.csv | Event scopes, parameters, and known synthetic factors | No; evaluation only |
| evaluation/insightx_record_labels.csv | Complete record labels and event memberships | No; evaluation only |
| evaluation/insightx_baseline.csv | Unchanged observations before injection | No; evaluation only |
| metadata.json | Config, environment, source identity, and CSV hashes | No; reproduction/evaluation only |

The business schema is exactly: record_id, date, region, product, category, customer_segment, units, price, discount, revenue, cost, orders, returns. Extra columns are rejected, including labels, hidden causes, and baseline values. Future loaders must open the business filename explicitly, not ingest the entire directory. File separation is not an access-control boundary.

## Configuration

| Option | Default | Meaning |
| --- | --- | --- |
| --seed | 42 | Non-negative deterministic seed |
| --start-date | 2024-01-01 | Inclusive start |
| --end-date | 2025-12-31 | Inclusive end |
| --rows | 100000 | Approximate row target |
| --no-anomalies | Off | Normal-only data |
| --no-seasonal-peaks | Off | Disable extra Nov/Dec peaks, retain monthly variation |
| --max-discount | 0.40 | Fractional cap, between 0 and 0.60 |
| --output-dir | data/synthetic under project root | Output folder |
| --overwrite | Off | Explicitly replace existing generated files |
| --validate-only | Off | Validate with the saved configuration in metadata |

```bash
python scripts/generate_dataset.py --seed 123 --rows 50000 --output-dir data/synthetic/seed123
python scripts/generate_dataset.py --no-anomalies --output-dir data/synthetic/normal
python scripts/generate_dataset.py --start-date 2023-01-01 --end-date 2024-12-31 --output-dir data/synthetic/alternate
python scripts/generate_dataset.py --validate-only --output-dir data/synthetic/seed123
python scripts/generate_dataset.py --help
```

All selected series appear every day. Series count is target rows divided by days, rounded to the nearest integer (halves round up), with a minimum of 30 to preserve product coverage. There are at most 600 series. Small targets may be raised substantially; targets above 600 x days fail. Anomaly injection needs at least 112 dates. Shorter ranges work with --no-anomalies.

Dataset settings use CLI arguments. Phase 1's .env settings remain unchanged; the generator reuses PROJECT_ROOT but does not need app settings or service credentials.

## Reproducibility and verification

Use the same config, generator source, Python, and dependencies. The four CSVs are byte-reproducible under those conditions. Metadata can differ when the recorded environment or Git state changes.

```bash
python --version
python -m pip freeze
git rev-parse HEAD
python scripts/generate_dataset.py --validate-only
```

metadata.json records config, exact row/series counts, generator version, source SHA-256, Git commit and dirty status, exact Python/package versions, and CSV SHA-256 hashes. A dirty build is explicitly marked. Saved-file validation checks hashes, business rules, labels, panel coverage, intervention replay, and baseline regeneration.

Actual verification on Linux/Python 3.12.14: **67 tests passed**, including all nine original unchanged Phase 1 tests. Default generation and saved-bundle validation passed. Health now checks NumPy/Pandas as well. No ML performance experiment has run. Raw command outputs are in [docs/phase2_checkpoint](docs/phase2_checkpoint).

Generated files are ignored by Git and recreated through the CLI. The committed dependency snapshot records the Linux test environment; it is not a universal cross-platform lockfile. Windows/macOS instructions were not executed here.

## Code layout

| Path | Purpose |
| --- | --- |
| insightx/config.py | Original settings and project root |
| insightx/health.py | Python, dependency, and settings checks |
| insightx/data/settings.py | Generation config and early validation |
| insightx/data/schema.py | Observation, event, and label contracts |
| insightx/data/generator.py | Vectorized normal behavior |
| insightx/data/anomalies.py | Event planning and interventions |
| insightx/data/validation.py | Business, panel, and ground-truth checks |
| insightx/data/io.py | CSV persistence, metadata, hashes, and replay |
| scripts/generate_dataset.py | Command-line entry point |
| tests/test_environment.py | Unchanged Phase 1 tests |
| tests/test_data_generation.py | Phase 2 tests |

## Troubleshooting

| Problem | Fix |
| --- | --- |
| Missing numpy/pandas | Activate .venv; run python -m pip install -r requirements.txt. |
| Unsupported Python | Recreate .venv with Python 3.12. |
| Health configuration error | Copy .env.example to .env; check APP_ENV/LOG_LEVEL and overriding process variables. |
| Output already exists | Use a new --output-dir or intentionally use --overwrite. |
| Invalid date/row settings | Use YYYY-MM-DD, at least 112 dates for anomalies, and no more than 600 series per date. |
| Requested/actual rows differ | Balanced-panel rounding is intentional; report the actual count from metadata. |
| Checksum mismatch | Preserve the edited file; regenerate into a new directory using the saved config. |
| Baseline replay differs | Restore the recorded generator source and Python/dependency environment. |
| Script not found | Run from project root or use the script's absolute path. |
| Git unavailable | Generation still works; metadata records unavailable Git revision and retains source hash/version. |

## Research scope

See [docs/phase2_research.md](docs/phase2_research.md) for generating equations, exact interventions, labels versus generating-factor truth, the default event ledger, and limitations. Synthetic ground truth does not establish real-world causality, generalization, novelty, patentability, or ML performance.

**Stop after Phase 2. Phase 3 requires explicit confirmation.**
