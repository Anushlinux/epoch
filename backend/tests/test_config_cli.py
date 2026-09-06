"""Configuration and CLI remain usable without credentials or a running server."""

import os
import subprocess
import sys

import pytest
from pydantic import ValidationError

from epoch_backend.config import Settings


@pytest.fixture(autouse=True)
def clear_epoch_environment(monkeypatch):
    for key in tuple(os.environ):
        if key.startswith("EPOCH_"):
            monkeypatch.delenv(key)


def run_cli(tmp_path, *args, overrides=None):
    env = {**os.environ, "EPOCH_DATA_DIR": str(tmp_path / "data"), **(overrides or {})}
    return subprocess.run(
        [sys.executable, "-m", "epoch_backend", *args],
        cwd=tmp_path,
        env=env,
        capture_output=True,
        text=True,
        timeout=15,
        check=False,
    )


def test_defaults_are_local_and_independent_of_working_directory(tmp_path, monkeypatch):
    before = Settings(_env_file=None)
    monkeypatch.chdir(tmp_path)
    after = Settings(_env_file=None)
    assert before.data_dir == after.data_dir
    assert after.data_dir.is_absolute()
    assert after.data_dir.name == "data"
    assert after.host == "127.0.0.1"
    assert after.port == 8000
    assert after.log_level == "info"
    assert set(after.cors_origins) == {"http://localhost:5173", "http://127.0.0.1:5173"}


def test_prefixed_environment_and_explicit_env_file_are_supported(tmp_path, monkeypatch):
    data_dir = tmp_path / "explicit-data"
    env_file = tmp_path / "backend.env"
    env_file.write_text(
        f'EPOCH_DATA_DIR="{data_dir.as_posix()}"\nEPOCH_PORT=8123\n', encoding="utf-8"
    )
    settings = Settings(_env_file=env_file)
    assert settings.data_dir == data_dir
    assert settings.port == 8123
    monkeypatch.setenv("EPOCH_PORT", "8124")
    assert Settings(_env_file=env_file).port == 8124


@pytest.mark.parametrize("host", ["0.0.0.0", "192.168.1.9", "example.com"])
def test_unauthenticated_foundation_rejects_non_loopback_binding(host, tmp_path):
    with pytest.raises(ValidationError):
        Settings(host=host, data_dir=tmp_path, _env_file=None)


@pytest.mark.parametrize("port", [0, 65536, "not-a-port"])
def test_invalid_ports_are_rejected(port, tmp_path):
    with pytest.raises(ValidationError):
        Settings(port=port, data_dir=tmp_path, _env_file=None)


def test_check_config_from_foreign_cwd_has_no_database_side_effects(tmp_path):
    result = run_cli(tmp_path, "check-config")
    assert result.returncode == 0, result.stdout + result.stderr
    assert not (tmp_path / "data").exists()


def test_importing_runtime_modules_has_no_storage_side_effects(tmp_path):
    env = {**os.environ, "EPOCH_DATA_DIR": str(tmp_path / "data")}
    result = subprocess.run(
        [sys.executable, "-c", "import epoch_backend.app; import epoch_backend.cli"],
        cwd=tmp_path,
        env=env,
        capture_output=True,
        text=True,
        timeout=15,
        check=False,
    )
    assert result.returncode == 0, result.stdout + result.stderr
    assert not (tmp_path / "data").exists()


def test_cli_explicit_env_file_selects_database_directory(tmp_path):
    data_dir = tmp_path / "selected-data"
    env_file = tmp_path / "backend.env"
    env_file.write_text(f'EPOCH_DATA_DIR="{data_dir.as_posix()}"\n', encoding="utf-8")
    env = {key: value for key, value in os.environ.items() if not key.startswith("EPOCH_")}
    result = subprocess.run(
        [sys.executable, "-m", "epoch_backend", "--env-file", str(env_file), "init-db"],
        cwd=tmp_path,
        env=env,
        capture_output=True,
        text=True,
        timeout=15,
        check=False,
    )
    assert result.returncode == 0, result.stdout + result.stderr
    assert (data_dir / "epoch.sqlite3").is_file()
    assert not (tmp_path / "data").exists()


def test_init_db_is_repeatable(tmp_path):
    first = run_cli(tmp_path, "init-db")
    assert first.returncode == 0, first.stdout + first.stderr
    database = tmp_path / "data" / "epoch.sqlite3"
    assert database.is_file()
    second = run_cli(tmp_path, "init-db")
    assert second.returncode == 0, second.stdout + second.stderr
    assert database.is_file()


@pytest.mark.parametrize(
    ("variable", "value", "field"),
    [
        ("EPOCH_PORT", "invalid", "port"),
        ("EPOCH_HOST", "0.0.0.0", "host"),
        ("EPOCH_CORS_ORIGINS", "malformed-json", "cors_origins"),
    ],
)
def test_cli_configuration_errors_are_clear_and_do_not_create_storage(
    tmp_path, variable, value, field
):
    result = run_cli(tmp_path, "check-config", overrides={variable: value})
    assert result.returncode == 2
    output = result.stdout + result.stderr
    assert field in output.lower()
    assert "Traceback" not in output
    assert not (tmp_path / "data").exists()


def test_cli_reports_unwritable_storage_without_success(tmp_path):
    obstructing_file = tmp_path / "not-a-directory"
    obstructing_file.write_text("preserve this file", encoding="utf-8")
    result = run_cli(tmp_path, "init-db", overrides={"EPOCH_DATA_DIR": str(obstructing_file)})
    assert result.returncode != 0
    assert "Traceback" not in result.stdout + result.stderr
    assert obstructing_file.read_text(encoding="utf-8") == "preserve this file"
