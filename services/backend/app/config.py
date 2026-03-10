import os
import re
from dataclasses import dataclass
from urllib.parse import urlparse


def _normalize_runpod_api_key(raw: str) -> str:
    key = raw.strip()
    if key.lower().startswith("bearer "):
        key = key.split(None, 1)[1].strip()
    return key


def _normalize_runpod_endpoint_id(raw: str) -> str:
    value = raw.strip().rstrip("/")
    if not value:
        return value

    if "://" in value:
        parsed = urlparse(value)
        path = parsed.path or ""
        match = re.search(r"/v2/([^/]+)", path)
        if match:
            return match.group(1)
        return value

    # Allow passing `/v2/<id>/run` or similar by mistake.
    match = re.search(r"/v2/([^/]+)", value)
    if match:
        return match.group(1)

    # If a full path-like value was passed, take the first non-empty segment.
    if "/" in value:
        return next((part for part in value.split("/") if part), value)

    return value


@dataclass(frozen=True)
class Settings:
    runpod_api_key: str
    runpod_endpoint_id: str
    runpod_base_url: str = "https://api.runpod.ai/v2"
    runpod_poll_interval_seconds: float = 8.0
    runpod_request_timeout_seconds: float = 3600.0

    @staticmethod
    def from_env() -> "Settings":
        api_key = _normalize_runpod_api_key(os.getenv("RUNPOD_API_KEY", ""))
        endpoint_id = _normalize_runpod_endpoint_id(os.getenv("RUNPOD_ENDPOINT_ID", ""))

        if not api_key:
            raise RuntimeError("RUNPOD_API_KEY is required")
        if not endpoint_id:
            raise RuntimeError("RUNPOD_ENDPOINT_ID is required")

        return Settings(
            runpod_api_key=api_key,
            runpod_endpoint_id=endpoint_id,
            runpod_base_url=os.getenv("RUNPOD_BASE_URL", "https://api.runpod.ai/v2").rstrip("/"),
            runpod_poll_interval_seconds=float(os.getenv("RUNPOD_POLL_INTERVAL_SECONDS", "8")),
            runpod_request_timeout_seconds=float(os.getenv("RUNPOD_REQUEST_TIMEOUT_SECONDS", "3600")),
        )
