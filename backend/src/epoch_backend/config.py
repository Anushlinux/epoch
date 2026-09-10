"""Explicit, validated local development settings."""

from pathlib import Path
from typing import Literal
from urllib.parse import urlsplit

from pydantic import Field, SecretStr, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

BACKEND_DIR = Path(__file__).resolve().parents[2]


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="EPOCH_", extra="forbid")

    data_dir: Path = BACKEND_DIR / "data"
    host: Literal["127.0.0.1", "localhost", "::1"] = "127.0.0.1"
    port: int = Field(default=8000, ge=1, le=65535)
    log_level: Literal["critical", "error", "warning", "info", "debug", "trace"] = "info"
    enable_hermes: bool = True
    chat_worker_idle_seconds: int = Field(default=300, ge=0, le=3600)
    pdf_image_id: str = ""

    @field_validator("pdf_image_id")
    @classmethod
    def validate_pdf_image(cls, value: str) -> str:
        import re
        if value and not re.fullmatch(r"sha256:[a-f0-9]{64}", value):
            raise ValueError("PDF image must be an immutable sha256 image ID")
        return value
    telemetry_enabled: bool = True
    ollama_base_url: str = "http://127.0.0.1:11434"
    trace_model: str = Field(default="qwen3:4b-instruct-2507-q4_K_M", min_length=1, max_length=200)
    trace_question_timeout_seconds: int = Field(default=180, ge=15, le=600)

    @field_validator("ollama_base_url")
    @classmethod
    def validate_ollama_url(cls, value: str) -> str:
        parsed = urlsplit(value)
        if (parsed.scheme != "http" or parsed.hostname not in {"127.0.0.1", "localhost", "::1"}
                or parsed.username is not None or parsed.password is not None
                or parsed.path not in {"", "/"} or parsed.query or parsed.fragment):
            raise ValueError("Ollama must use a loopback HTTP origin without credentials or a path")
        port = parsed.port if parsed.port is not None else 11434
        if port == 0:
            raise ValueError("Ollama port must be between 1 and 65535")
        # Resolve the localhost spelling ourselves; requests never use a DNS name.
        host = "[::1]" if parsed.hostname == "::1" else "127.0.0.1"
        return f"http://{host}:{port}"

    @field_validator("trace_model")
    @classmethod
    def validate_trace_model(cls, value: str) -> str:
        value = value.strip()
        if not value or any(char.isspace() for char in value) or "cloud" in value.lower() or "://" in value:
            raise ValueError("Use the exact name of an installed local Ollama model")
        return value

    neatlogs_cloud_enabled: bool = False
    neatlogs_api_key: SecretStr = Field(
        default=SecretStr(""), validation_alias="NEATLOGS_API_KEY", exclude=True, repr=False
    )
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
