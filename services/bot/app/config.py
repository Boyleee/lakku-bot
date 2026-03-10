import os
from dataclasses import dataclass


@dataclass(frozen=True)
class Settings:
    telegram_bot_token: str
    backend_base_url: str
    poll_interval_seconds: float
    status_update_seconds: float

    @staticmethod
    def from_env() -> "Settings":
        token = os.getenv("TELEGRAM_BOT_TOKEN", "").strip()
        if not token:
            raise RuntimeError("TELEGRAM_BOT_TOKEN is required")

        return Settings(
            telegram_bot_token=token,
            backend_base_url=os.getenv("BACKEND_BASE_URL", "http://backend:8000").rstrip("/"),
            poll_interval_seconds=float(os.getenv("BOT_POLL_INTERVAL_SECONDS", "8")),
            status_update_seconds=float(os.getenv("BOT_STATUS_UPDATE_SECONDS", "45")),
        )
