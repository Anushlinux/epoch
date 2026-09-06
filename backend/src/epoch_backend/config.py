"""Explicit, validated local development settings."""

from pathlib import Path
from typing import Literal
from urllib.parse import urlsplit

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

BACKEND_DIR = Path(__file__).resolve().parents[2]


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="EPOCH_", extra="forbid")

    data_dir: Path = BACKEND_DIR / "data"
    host: Literal["127.0.0.1", "localhost", "::1"] = "127.0.0.1"
    port: int = Field(default=8000, ge=1, le=65535)
    log_level: Literal["critical", "error", "warning", "info", "debug", "trace"] = "info"
    enable_hermes: bool = True
    telemetry_enabled: bool = True
    neatlogs_cloud_enabled: bool = False
    repair_image: str = (
        "python:3.12-slim@sha256:78387bc3881b8273120a12ebe6c1ab22b018ccc2c9adf565ae1ac9b536e184ea"
    )

    @field_validator("repair_image")
    @classmethod
    def validate_repair_image(cls, value: str) -> str:
        import re

        if not re.fullmatch(r"[A-Za-z0-9._/:-]+@sha256:[a-f0-9]{64}", value):
            raise ValueError("repair image must be pinned to a sha256 digest")
        return value

    cors_origins: list[str] = Field(
        default_factory=lambda: ["http://localhost:5173", "http://127.0.0.1:5173"]
    )

    @field_validator("data_dir", mode="before")
    @classmethod
    def resolve_data_dir(cls, value: object) -> Path:
        if not isinstance(value, (str, Path)) or not str(value).strip():
            raise ValueError("must be a nonblank directory path")
        path = Path(value).expanduser()
        return (path if path.is_absolute() else BACKEND_DIR / path).resolve()

    @field_validator("cors_origins")
    @classmethod
    def validate_origins(cls, origins: list[str]) -> list[str]:
        for origin in origins:
            parsed = urlsplit(origin)
            if (
                parsed.scheme not in {"http", "https"}
                or parsed.hostname not in {"localhost", "127.0.0.1", "::1"}
                or parsed.username is not None
                or parsed.password is not None
                or parsed.path
                or parsed.query
                or parsed.fragment
            ):
                raise ValueError("origins must be exact loopback HTTP(S) origins without a path")
            # Accessing .port validates malformed and out-of-range ports.
            _ = parsed.port
        return list(dict.fromkeys(origins))

    @property
    def database_path(self) -> Path:
        return self.data_dir / "epoch.sqlite3"
