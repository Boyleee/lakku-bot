from __future__ import annotations

import asyncio
import logging
from typing import Any

from fastapi import FastAPI, HTTPException
from fastapi.responses import Response

from .config import Settings
from .constants import (
    DEFAULT_FLOW_SHIFT,
    DEFAULT_GUIDANCE_SCALE,
    DEFAULT_GUIDANCE_SCALE_2,
    DEFAULT_NEGATIVE_PROMPT,
    DEFAULT_SCHEDULER,
)
from .media import extract_video_payload
from .runpod_client import RunPodClient, RunPodConfig
from .schemas import GenerationRequest, JobCreatedResponse, JobStatusResponse
from .store import JobStore

logger = logging.getLogger("wan-backend")
logging.basicConfig(level=logging.INFO)

app = FastAPI(title="Wan2.2 Telegram Backend", version="0.1.0")

settings = Settings.from_env()
store = JobStore()
runpod_client = RunPodClient(
    RunPodConfig(
        base_url=settings.runpod_base_url,
        endpoint_id=settings.runpod_endpoint_id,
        api_key=settings.runpod_api_key,
        poll_interval_seconds=settings.runpod_poll_interval_seconds,
        request_timeout_seconds=settings.runpod_request_timeout_seconds,
    )
)


def _build_runpod_payload(request: GenerationRequest) -> dict[str, Any]:
    return {
        "input_image_base64": request.input_image_base64,
        "last_image_base64": request.last_image_base64,
        "prompt": request.prompt,
        "duration_seconds": request.duration_seconds,
        "fps": request.fps,
        "inference_steps": request.inference_steps,
        "video_quality": request.video_quality,
        # Fixed to HF Space UI defaults to keep generation behavior aligned.
        "negative_prompt": DEFAULT_NEGATIVE_PROMPT,
        "guidance_scale": DEFAULT_GUIDANCE_SCALE,
        "guidance_scale_2": DEFAULT_GUIDANCE_SCALE_2,
        "scheduler": DEFAULT_SCHEDULER,
        "flow_shift": DEFAULT_FLOW_SHIFT,
    }


async def _process_job(job_id: str, request: GenerationRequest) -> None:
    try:
        submission = await runpod_client.submit(_build_runpod_payload(request))
        await store.mark_running(job_id, submission.id)
        output = await runpod_client.wait_for_completion(submission.id)

        video_payload = await extract_video_payload(output)
        output_dict = output if isinstance(output, dict) else {}

        await store.mark_completed(
            job_id,
            video_bytes=video_payload.data,
            video_mime_type=video_payload.mime_type,
            seed=output_dict.get("seed"),
            fps=output_dict.get("fps"),
            duration_seconds=output_dict.get("duration_seconds"),
            width=output_dict.get("width"),
            height=output_dict.get("height"),
        )
        logger.info("Job %s completed", job_id)
    except Exception as exc:  # noqa: BLE001
        logger.exception("Job %s failed", job_id)
        await store.mark_failed(job_id, str(exc))


@app.get("/healthz")
async def healthz() -> dict[str, str]:
    return {"status": "ok"}


@app.post("/api/v1/jobs", response_model=JobCreatedResponse)
async def create_job(request: GenerationRequest) -> JobCreatedResponse:
    record = await store.create()
    asyncio.create_task(_process_job(record.job_id, request))
    return JobCreatedResponse(job_id=record.job_id, status=record.status)


@app.get("/api/v1/jobs/{job_id}", response_model=JobStatusResponse)
async def get_job(job_id: str) -> JobStatusResponse:
    record = await store.get(job_id)
    if record is None:
        raise HTTPException(status_code=404, detail="Job not found")

    return JobStatusResponse(
        job_id=record.job_id,
        status=record.status,
        runpod_job_id=record.runpod_job_id,
        error=record.error,
        seed=record.seed,
        fps=record.fps,
        duration_seconds=record.duration_seconds,
        width=record.width,
        height=record.height,
    )


@app.get("/api/v1/jobs/{job_id}/video")
async def get_job_video(job_id: str) -> Response:
    record = await store.get(job_id)
    if record is None:
        raise HTTPException(status_code=404, detail="Job not found")

    if record.status != "completed" or not record.video_bytes:
        raise HTTPException(status_code=409, detail="Video is not ready")

    filename = f"wan22-{job_id}.mp4"
    headers = {"Content-Disposition": f'attachment; filename="{filename}"'}
    return Response(content=record.video_bytes, media_type=record.video_mime_type or "video/mp4", headers=headers)
