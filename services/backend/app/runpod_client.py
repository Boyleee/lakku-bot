from __future__ import annotations

import asyncio
import time
from dataclasses import dataclass
from typing import Any

import httpx

from .schemas import RunPodStatusResponse, RunPodSubmissionResponse

TERMINAL_STATUSES = {"COMPLETED", "FAILED", "CANCELLED", "TIMED_OUT"}
SUCCESS_STATUS = "COMPLETED"


class RunPodError(RuntimeError):
    """Base exception for RunPod integration issues."""


class RunPodJobFailed(RunPodError):
    """Raised when RunPod finishes with a failed status."""


class RunPodTimeout(RunPodError):
    """Raised when RunPod polling times out."""


@dataclass(frozen=True)
class RunPodConfig:
    base_url: str
    endpoint_id: str
    api_key: str
    poll_interval_seconds: float
    request_timeout_seconds: float


class RunPodClient:
    def __init__(self, config: RunPodConfig):
        self._config = config
        self._headers = {
            "Authorization": f"Bearer {config.api_key}",
            "Content-Type": "application/json",
        }

    @staticmethod
    def _raise_for_status_with_hint(response: httpx.Response, *, path: str) -> None:
        try:
            response.raise_for_status()
        except httpx.HTTPStatusError as exc:
            status_code = exc.response.status_code
            body = exc.response.text.strip().replace("\n", " ")
            body = body[:400] if body else "<empty>"

            if status_code in (401, 403):
                hint = (
                    "Проверьте RUNPOD_API_KEY: ключ должен быть активным, с правами запуска serverless "
                    "(read/write), и принадлежать тому же workspace/organization, что и endpoint. "
                    "Передавайте ключ без префикса 'Bearer '."
                )
            elif status_code == 404:
                hint = "Проверьте RUNPOD_ENDPOINT_ID (можно указывать только id без URL)."
            else:
                hint = "Проверьте логи RunPod endpoint и корректность входных параметров."

            raise RunPodError(
                f"RunPod HTTP {status_code} on '{path}'. {hint} Response: {body}"
            ) from exc

    async def _post(self, path: str, payload: dict[str, Any]) -> dict[str, Any]:
        timeout = httpx.Timeout(60)
        async with httpx.AsyncClient(timeout=timeout) as client:
            response = await client.post(
                f"{self._config.base_url}/{self._config.endpoint_id}/{path}",
                headers=self._headers,
                json=payload,
            )
            self._raise_for_status_with_hint(response, path=path)
            return response.json()

    async def _get(self, path: str) -> dict[str, Any]:
        timeout = httpx.Timeout(60)
        async with httpx.AsyncClient(timeout=timeout) as client:
            response = await client.get(
                f"{self._config.base_url}/{self._config.endpoint_id}/{path}",
                headers=self._headers,
            )
            self._raise_for_status_with_hint(response, path=path)
            return response.json()

    async def submit(self, model_input: dict[str, Any]) -> RunPodSubmissionResponse:
        data = await self._post("run", {"input": model_input})
        parsed = RunPodSubmissionResponse.model_validate(data)
        return parsed

    async def get_status(self, runpod_job_id: str) -> RunPodStatusResponse:
        data = await self._get(f"status/{runpod_job_id}")
        return RunPodStatusResponse.model_validate(data)

    async def wait_for_completion(self, runpod_job_id: str) -> Any:
        deadline = time.monotonic() + self._config.request_timeout_seconds
        while True:
            status_response = await self.get_status(runpod_job_id)
            status = status_response.status.upper()

            if status == SUCCESS_STATUS:
                return status_response.output

            if status in TERMINAL_STATUSES and status != SUCCESS_STATUS:
                error = status_response.error or f"RunPod job ended with status {status}"
                raise RunPodJobFailed(error)

            if time.monotonic() > deadline:
                raise RunPodTimeout(
                    f"RunPod job {runpod_job_id} timed out after {self._config.request_timeout_seconds:.0f}s"
                )

            await asyncio.sleep(self._config.poll_interval_seconds)

    async def run_and_wait(self, model_input: dict[str, Any]) -> tuple[str, Any]:
        submission = await self.submit(model_input)
        output = await self.wait_for_completion(submission.id)
        return submission.id, output
