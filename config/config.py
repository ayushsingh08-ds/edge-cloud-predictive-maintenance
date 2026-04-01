from __future__ import annotations

import os
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path

from dotenv import load_dotenv

ROOT_DIR = Path(__file__).resolve().parents[1]
ENV_PATH = ROOT_DIR / ".env"

load_dotenv(dotenv_path=ENV_PATH, override=False)


@dataclass(frozen=True)
class Settings:
    db_host: str
    db_name: str
    db_user: str
    db_pass: str
    rabbitmq_host: str
    rabbitmq_user: str
    rabbitmq_pass: str
    api_host: str
    api_port: int
    use_rabbitmq: bool
    enable_event_consumers: bool

    @property
    def database_url(self) -> str:
        return (
            f"postgresql+psycopg2://{self.db_user}:{self.db_pass}"
            f"@{self.db_host}:5432/{self.db_name}"
        )


REQUIRED_KEYS = {
    "DB_HOST",
    "DB_NAME",
    "DB_USER",
    "DB_PASS",
    "RABBITMQ_HOST",
    "RABBITMQ_USER",
    "RABBITMQ_PASS",
    "API_HOST",
    "API_PORT",
}


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    missing = [key for key in REQUIRED_KEYS if not os.getenv(key)]
    if missing:
        missing_str = ", ".join(sorted(missing))
        raise ValueError(f"Missing required environment variables: {missing_str}")

    return Settings(
        db_host=os.environ["DB_HOST"],
        db_name=os.environ["DB_NAME"],
        db_user=os.environ["DB_USER"],
        db_pass=os.environ["DB_PASS"],
        rabbitmq_host=os.environ["RABBITMQ_HOST"],
        rabbitmq_user=os.environ["RABBITMQ_USER"],
        rabbitmq_pass=os.environ["RABBITMQ_PASS"],
        api_host=os.environ["API_HOST"],
        api_port=int(os.environ["API_PORT"]),
        use_rabbitmq=os.getenv("USE_RABBITMQ", "true").lower() == "true",
        enable_event_consumers=os.getenv("ENABLE_EVENT_CONSUMERS", "false").lower() == "true",
    )
