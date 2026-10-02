"""Run with python -m insightx.health from the project root."""

import importlib
import platform
import sys
from importlib.metadata import version

DEPENDENCIES = {
    "python-dotenv": "dotenv", "pytest": "pytest",
    "numpy": "numpy", "pandas": "pandas",
}


def main() -> int:
    """Print safe diagnostics and return a nonzero exit code on failure."""
    print(f"Python: {platform.python_version()}")
    if sys.version_info[:2] != (3, 12):
        print("FAIL: Phase 1 targets Python 3.12.x.")
        return 1
    for distribution, module in DEPENDENCIES.items():
        try:
            importlib.import_module(module)
            installed_version = version(distribution)
        except Exception as exc:
            print(f"FAIL: {distribution} is unavailable ({type(exc).__name__}).")
            print("Run: python -m pip install -r requirements.txt")
            return 1
        print(f"OK: {distribution} {installed_version}")
    try:
        from insightx.config import load_settings

        settings = load_settings()
    except (ValueError, OSError) as exc:
        print(f"FAIL: configuration error ({type(exc).__name__}).")
        print("Copy .env.example to .env and check APP_ENV and LOG_LEVEL.")
        return 1
    print(f"OK: environment={settings.app_env}, log_level={settings.log_level}")
    print("InsightX Phase 1 health check: PASS")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
