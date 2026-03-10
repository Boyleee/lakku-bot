from __future__ import annotations

import base64
import io
import os
from typing import Any

import runpod
from PIL import Image
from pydantic import BaseModel, Field, field_validator

from generation import (
    DEFAULT_NEGATIVE_PROMPT,
    DEFAULT_PROMPT_I2V,
    MAX_DURATION,
    MAX_FRAMES_MODEL,
    MAX_SEED,
    MIN_DURATION,
    MIN_FRAMES_MODEL,
    Wan22Generator,
)


class GenerationInput(BaseModel):
    input_image_base64: str
    prompt: str = DEFAULT_PROMPT_I2V
    duration_seconds: float = Field(default=3.5, ge=MIN_DURATION, le=MAX_DURATION)
    fps: int = Field(default=16)
    inference_steps: int = Field(default=6, ge=1, le=30)
    video_quality: int = Field(default=6, ge=1, le=10)
    last_image_base64: str | None = None

    negative_prompt: str = DEFAULT_NEGATIVE_PROMPT
    guidance_scale: float = 1.0
    guidance_scale_2: float = 1.0
    scheduler: str = "UniPCMultistep"
    flow_shift: float = 3.0
    seed: int | None = Field(default=None, ge=0, le=MAX_SEED)

    @field_validator("fps")
    @classmethod
    def validate_fps(cls, value: int) -> int:
        if value not in (16, 32, 64):
            raise ValueError("fps must be one of: 16, 32, 64")
        return value

    @field_validator("input_image_base64", "last_image_base64")
    @classmethod
    def validate_base64_presence(cls, value: str | None) -> str | None:
        if value is None:
            return value
        if not value.strip():
            raise ValueError("base64 image must not be empty")
        return value


def _decode_base64_image(raw: str) -> Image.Image:
    payload = raw
    if raw.startswith("data:"):
        payload = raw.split(",", 1)[1]

    decoded = base64.b64decode(payload)
    with Image.open(io.BytesIO(decoded)) as image:
        return image.convert("RGB")


GENERATOR: Wan22Generator | None = None


def _get_generator() -> Wan22Generator:
    global GENERATOR
    if GENERATOR is None:
        GENERATOR = Wan22Generator()
    return GENERATOR


def handler(job: dict[str, Any]) -> dict[str, Any]:
    payload = GenerationInput.model_validate(job.get("input") or {})

    input_image = _decode_base64_image(payload.input_image_base64)
    last_image = _decode_base64_image(payload.last_image_base64) if payload.last_image_base64 else None

    result = _get_generator().generate(
        input_image=input_image,
        last_image=last_image,
        prompt=payload.prompt,
        steps=payload.inference_steps,
        duration_seconds=payload.duration_seconds,
        quality=payload.video_quality,
        frame_multiplier=payload.fps,
        negative_prompt=payload.negative_prompt,
        guidance_scale=payload.guidance_scale,
        guidance_scale_2=payload.guidance_scale_2,
        scheduler=payload.scheduler,
        flow_shift=payload.flow_shift,
        seed=payload.seed,
    )

    with open(result.video_path, "rb") as f:
        video_base64 = base64.b64encode(f.read()).decode("utf-8")

    if os.path.exists(result.video_path):
        os.remove(result.video_path)

    return {
        "video_base64": video_base64,
        "mime_type": "video/mp4",
        "seed": result.seed,
        "fps": result.fps,
        "duration_seconds": result.duration_seconds,
        "width": result.width,
        "height": result.height,
        "min_frames_model": MIN_FRAMES_MODEL,
        "max_frames_model": MAX_FRAMES_MODEL,
    }


runpod.serverless.start({"handler": handler})
