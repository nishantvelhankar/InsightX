"""Verify configuration precedence and useful health-check failures."""

import pytest

from insightx import health
from insightx.config import Settings, load_settings


@pytest.fixture(autouse=True)
def clean_environment(monkeypatch):
    for key in ("APP_ENV", "LOG_LEVEL"):
        monkeypatch.delenv(key, raising=False)


def test_load_env_file(tmp_path):
    env_file = tmp_path / ".env"
    env_file.write_text("APP_ENV=development\nLOG_LEVEL=info\n", encoding="utf-8")
    assert load_settings(env_file) == Settings("development", "INFO")


def test_environment_overrides_file(tmp_path, monkeypatch):
    env_file = tmp_path / ".env"
    env_file.write_text("APP_ENV=development\nLOG_LEVEL=INFO\n", encoding="utf-8")
    monkeypatch.setenv("APP_ENV", "test")
    assert load_settings(env_file).app_env == "test"


@pytest.mark.parametrize("content", [
    "APP_ENV=invalid\nLOG_LEVEL=INFO\n",
    "APP_ENV=test\nLOG_LEVEL=invalid\n",
])
def test_invalid_settings(tmp_path, content):
    env_file = tmp_path / ".env"
    env_file.write_text(content, encoding="utf-8")
    with pytest.raises(ValueError):
        load_settings(env_file)


def test_missing_settings(tmp_path):
    with pytest.raises(ValueError):
        load_settings(tmp_path / "missing.env")


def test_health_success(monkeypatch, capsys):
    monkeypatch.setenv("APP_ENV", "test")
    monkeypatch.setenv("LOG_LEVEL", "INFO")
    assert health.main() == 0
    assert "health check: PASS" in capsys.readouterr().out


def test_health_missing_dependency(monkeypatch, capsys):
    def missing_module(name):
        raise ModuleNotFoundError(name)

    monkeypatch.setattr(health.importlib, "import_module", missing_module)
    assert health.main() == 1
    assert "pip install -r requirements.txt" in capsys.readouterr().out


def test_health_invalid_configuration(monkeypatch, capsys):
    monkeypatch.setenv("APP_ENV", "invalid")
    monkeypatch.setenv("LOG_LEVEL", "INFO")
    assert health.main() == 1
    assert "configuration error" in capsys.readouterr().out


def test_health_wrong_python(monkeypatch, capsys):
    monkeypatch.setattr(health.sys, "version_info", (3, 11, 0))
    assert health.main() == 1
    assert "targets Python 3.12.x" in capsys.readouterr().out
