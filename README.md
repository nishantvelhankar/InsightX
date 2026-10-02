# InsightX — Phase 1

An Evidence-Guided Agentic Framework for Reliable GenAI-Based Investigation of Anomalies in Structured Data.

## What this phase builds and why

This phase creates a Python 3.12 environment, a small importable package, validated environment settings, a command-line health check, and tests. These provide a repeatable foundation and catch setup errors before research functionality is added.

Only python-dotenv and Pytest are installed. Exact direct dependency versions are fixed in requirements.txt; this is not a complete transitive lockfile. Pandas, NumPy, Scikit-learn, PostgreSQL, FastAPI, Streamlit, Plotly, and an LLM SDK will be added in their implementation phases. No database installation, API key, dataset, model, agent, or dashboard is needed now.

## Prerequisites

Install Python 3.12.x from https://www.python.org/downloads/ and Git from https://git-scm.com/downloads if absent. Use an up-to-date patch release in the 3.12 series. Internet access is needed for pip installation. Extract insightx-phase1.zip; the archive contains an insightx folder. Run commands from its parent directory first.

## Windows Command Prompt (cmd.exe)

```bat
cd insightx
py -3.12 --version
git --version
py -3.12 -m venv .venv
.venv\Scripts\activate.bat
python -m pip install -r requirements.txt
copy .env.example .env
python --version
python -m pip check
python -m insightx.health
python -m pytest -q
git init
git status --short --untracked-files=all
```

For PowerShell, replace activation with `.\.venv\Scripts\Activate.ps1` and the copy command with `Copy-Item .env.example .env`. If script execution is blocked, run the commands in Command Prompt, or invoke `.\.venv\Scripts\python.exe` in place of `python` without activation. Do not overwrite an existing customized .env when repeating setup.

## macOS or Linux

```bash
cd insightx
python3.12 --version
git --version
python3.12 -m venv .venv
source .venv/bin/activate
python -m pip install -r requirements.txt
cp .env.example .env
python --version
python -m pip check
python -m insightx.health
python -m pytest -q
git init
git status --short --untracked-files=all
```

The .venv, .env, caches, generated data, and reports should not appear in Git's untracked-file listing. Never put credentials in tracked files. A future API integration will add empty credential placeholders and load credentials from .env. The present .env contains only APP_ENV and LOG_LEVEL.

## Verification and expected output

Run from the project root with the virtual environment active:

```bash
python --version
python -m pip check
python -m insightx.health
python -m pytest -q
```

Expected output (Python patch and timing can differ):

```text
Python 3.12.x
No broken requirements found.
Python: 3.12.x
OK: python-dotenv 1.1.0
OK: pytest 8.3.5
OK: environment=development, log_level=INFO
InsightX Phase 1 health check: PASS
......... [100%]
9 passed in <elapsed time>s
```

The health command exits with code 0 for success or 1 for failure. It checks the target Python series, imports the two dependencies, reports installed versions, and validates configuration. `pip check` checks installed dependency compatibility. The health check does not contact external services or verify future application features.

Settings come from the project-root .env file, with process environment variables taking precedence. APP_ENV accepts development, test, or production. LOG_LEVEL accepts DEBUG, INFO, WARNING, ERROR, or CRITICAL. Missing or invalid settings fail explicitly. Tests use temporary files and isolated settings.

## Conceptual test walkthrough

1. A valid .env loads and normalizes the log level.
2. A process APP_ENV overrides the file value.
3. An invalid APP_ENV raises ValueError.
4. An invalid LOG_LEVEL raises ValueError.
5. Missing settings raise ValueError.
6. Valid configuration and imports produce health PASS and exit 0.
7. A simulated missing dependency produces a repair command and exit 1.
8. Invalid configuration produces a safe message and exit 1.
9. A simulated unsupported Python version produces exit 1.

These nine cases should pass in a correctly installed Python 3.12 environment. They do not constitute evidence that the research hypothesis is true.

## Common errors and fixes

| Symptom | Fix |
| --- | --- |
| Python or py is not recognized | Install Python 3.12, enable PATH integration where offered, and reopen the terminal. |
| python3.12 is missing | Install Python 3.12 through your platform's supported installer. |
| venv or ensurepip is unavailable on Linux | Install your distribution's Python 3.12 venv support, then recreate .venv. |
| No module named insightx | Change into the folder containing README.md and the inner insightx package. |
| dotenv or pytest cannot be imported | Use the virtual environment's Python and rerun `python -m pip install -r requirements.txt`. |
| pip download fails | Check network/proxy configuration and retry; do not disable TLS verification. |
| Configuration error | Copy .env.example to .env; check APP_ENV and LOG_LEVEL, including process variables that override the file. |
| Unsupported Python | Recreate .venv with Python 3.12 and reinstall requirements. |
| git is not recognized | Install Git and reopen the terminal. |

## Files

| File | Purpose |
| --- | --- |
| README.md | Setup, commands, expected results, and troubleshooting |
| requirements.txt | Direct Phase 1 dependency pins |
| pytest.ini | Test discovery configuration |
| .env.example | Safe environment template |
| .gitignore | Excludes local environments, secrets, and generated output |
| insightx/__init__.py | Package identity and version |
| insightx/config.py | Environment settings and validation |
| insightx/health.py | Executable environment verification |
| tests/test_environment.py | Nine setup and failure-path tests |
| docs/research_notes.md | Research question, boundaries, and reproducibility checklist |
| data/raw/.gitkeep | Empty input-data folder marker |
| data/processed/.gitkeep | Empty processed-data folder marker |
| reports/.gitkeep | Empty report folder marker |

Setup creates .venv and .env locally. Test runs create ignored caches. No future feature modules are stubbed out as if implemented.

## Next step

Complete and verify Phase 1. Stop here and request confirmation before starting another phase.
