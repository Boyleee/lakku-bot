from __future__ import annotations

import asyncio
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Literal
from uuid import uuid4


JobStatus = Literal["queued", "running", "completed", "failed"]


@dataclass
class JobRecord:
    job_id: str
    status: JobStatus
    created_at: datetime = field(default_factory=lambda: datetime.now(tz=timezone.utc))
    updated_at: datetime = field(default_factory=lambda: datetime.now(tz=timezone.utc))
    runpod_job_id: str | None = None
    error: str | None = None
    video_bytes: bytes | None = None
    video_mime_type: str | None = None
    seed: int | None = None
    fps: int | None = None
    duration_seconds: float | None = None
    width: int | None = None
    height: int | None = None


class JobStore:
    def __init__(self) -> None:
        self._jobs: dict[str, JobRecord] = {}
        self._lock = asyncio.Lock()

    async def create(self) -> JobRecord:
        async with self._lock:
            job_id = uuid4().hex
            record = JobRecord(job_id=job_id, status="queued")
            self._jobs[job_id] = record
            return record

    async def get(self, job_id: str) -> JobRecord | None:
        async with self._lock:
            return self._jobs.get(job_id)

    async def mark_running(self, job_id: str, runpod_job_id: str) -> None:
        async with self._lock:
            record = self._jobs[job_id]
            record.status = "running"
            record.runpod_job_id = runpod_job_id
            record.updated_at = datetime.now(tz=timezone.utc)

    async def mark_completed(
        self,
        job_id: str,
        *,
        video_bytes: bytes,
        video_mime_type: str,
        seed: int | None,
        fps: int | None,
        duration_seconds: float | None,
        width: int | None,
        height: int | None,
    ) -> None:
        async with self._lock:
            record = self._jobs[job_id]
            record.status = "completed"
            record.video_bytes = video_bytes
            record.video_mime_type = video_mime_type
            record.seed = seed
            record.fps = fps
            record.duration_seconds = duration_seconds
            record.width = width
            record.height = height
            record.updated_at = datetime.now(tz=timezone.utc)

    async def mark_failed(self, job_id: str, error: str) -> None:
        async with self._lock:
            record = self._jobs[job_id]
            record.status = "failed"
            record.error = error
            record.updated_at = datetime.now(tz=timezone.utc)
