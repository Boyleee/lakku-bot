import os
from dataclasses import dataclass


@dataclass(frozen=True)
class Settings:
    runpod_api_key: str
    runpod_endpoint_id: str
    runpod_base_url: str = "https://api.runpod.ai/v2"
    runpod_poll_interval_seconds: float = 8.0
    runpod_request_timeout_seconds: float = 3600.0

    @staticmethod
    def from_env() -> "Settings":
        api_key = os.getenv("RUNPOD_API_KEY", "").strip()
        endpoint_id = os.getenv("RUNPOD_ENDPOINT_ID", "").strip()

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
