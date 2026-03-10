from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import httpx


class BackendApiError(RuntimeError):
    """Raised when backend API returns an invalid response."""


@dataclass(frozen=True)
class JobStatus:
    job_id: str
    status: str
    error: str | None
    seed: int | None


class BackendClient:
    def __init__(self, base_url: str):
        self._base_url = base_url

    async def submit_job(self, payload: dict[str, Any]) -> str:
        try:
            async with httpx.AsyncClient(timeout=httpx.Timeout(60)) as client:
                response = await client.post(f"{self._base_url}/api/v1/jobs", json=payload)
                response.raise_for_status()
                data = response.json()
        except httpx.TimeoutException as exc:
            raise BackendApiError("Timeout при отправке задачи в backend.") from exc
        except httpx.HTTPError as exc:
            raise BackendApiError(f"Ошибка backend при отправке задачи: {exc}") from exc

        job_id = data.get("job_id")
        if not isinstance(job_id, str):
            raise BackendApiError("Invalid backend response: missing job_id")
        return job_id

    async def get_job_status(self, job_id: str) -> JobStatus:
        try:
            async with httpx.AsyncClient(timeout=httpx.Timeout(60)) as client:
                response = await client.get(f"{self._base_url}/api/v1/jobs/{job_id}")
                response.raise_for_status()
                data = response.json()
        except httpx.TimeoutException as exc:
            raise BackendApiError("Timeout при получении статуса задачи из backend.") from exc
        except httpx.HTTPError as exc:
            raise BackendApiError(f"Ошибка backend при получении статуса: {exc}") from exc

        status = data.get("status")
        if not isinstance(status, str):
            raise BackendApiError("Invalid backend response: missing status")

        return JobStatus(
            job_id=job_id,
            status=status,
            error=data.get("error"),
            seed=data.get("seed"),
        )

    async def download_video(self, job_id: str) -> bytes:
        try:
            async with httpx.AsyncClient(timeout=httpx.Timeout(900)) as client:
                response = await client.get(f"{self._base_url}/api/v1/jobs/{job_id}/video")
                response.raise_for_status()
                return response.content
        except httpx.TimeoutException as exc:
            raise BackendApiError("Timeout при скачивании видео из backend.") from exc
        except httpx.HTTPError as exc:
            raise BackendApiError(f"Ошибка backend при скачивании видео: {exc}") from exc
