from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, Field, field_validator

from .constants import (
    DEFAULT_DURATION_SECONDS,
    DEFAULT_INFERENCE_STEPS,
    DEFAULT_PROMPT_I2V,
    DEFAULT_VIDEO_QUALITY,
    FPS_CHOICES,
    MAX_DURATION_SECONDS,
    MAX_INFERENCE_STEPS,
    MAX_VIDEO_QUALITY,
    MIN_DURATION_SECONDS,
    MIN_INFERENCE_STEPS,
    MIN_VIDEO_QUALITY,
)


class GenerationRequest(BaseModel):
    input_image_base64: str = Field(..., description="Base64 string for the input image")
    prompt: str = Field(default=DEFAULT_PROMPT_I2V)
    duration_seconds: float = Field(default=DEFAULT_DURATION_SECONDS, ge=MIN_DURATION_SECONDS, le=MAX_DURATION_SECONDS)
    fps: int = Field(default=FPS_CHOICES[0])
    inference_steps: int = Field(default=DEFAULT_INFERENCE_STEPS, ge=MIN_INFERENCE_STEPS, le=MAX_INFERENCE_STEPS)
    video_quality: int = Field(default=DEFAULT_VIDEO_QUALITY, ge=MIN_VIDEO_QUALITY, le=MAX_VIDEO_QUALITY)
    last_image_base64: str | None = None

    @field_validator("input_image_base64", "last_image_base64")
    @classmethod
    def base64_must_not_be_empty(cls, value: str | None) -> str | None:
        if value is None:
            return value
        if not value.strip():
            raise ValueError("base64 image value cannot be empty")
        return value

    @field_validator("fps")
    @classmethod
    def fps_must_be_supported(cls, value: int) -> int:
        if value not in FPS_CHOICES:
            raise ValueError(f"fps must be one of: {', '.join(map(str, FPS_CHOICES))}")
        return value


class JobCreatedResponse(BaseModel):
    job_id: str
    status: Literal["queued", "running", "completed", "failed"]


class JobStatusResponse(BaseModel):
    job_id: str
    status: Literal["queued", "running", "completed", "failed"]
    runpod_job_id: str | None = None
    error: str | None = None
    seed: int | None = None
    fps: int | None = None
    duration_seconds: float | None = None
    width: int | None = None
    height: int | None = None


class RunPodSubmissionResponse(BaseModel):
    id: str
    status: str


class RunPodStatusResponse(BaseModel):
    id: str
    status: str
    output: Any = None
    error: str | None = None
