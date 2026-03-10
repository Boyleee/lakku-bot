from __future__ import annotations

import base64
from dataclasses import dataclass
from typing import Any

import httpx


@dataclass(frozen=True)
class VideoPayload:
    data: bytes
    mime_type: str


def _strip_data_uri_prefix(value: str) -> tuple[str, str]:
    if not value.startswith("data:"):
        return value, "video/mp4"

    header, encoded = value.split(",", 1)
    mime = "video/mp4"
    if ";" in header:
        mime = header.split(";", 1)[0].split(":", 1)[1]
    return encoded, mime


def _decode_base64(value: str) -> VideoPayload:
    encoded, mime = _strip_data_uri_prefix(value)
    try:
        return VideoPayload(data=base64.b64decode(encoded), mime_type=mime)
    except Exception as exc:  # pragma: no cover - defensive
        raise ValueError("Invalid base64 video data from RunPod output") from exc


async def _download_video(url: str) -> VideoPayload:
    async with httpx.AsyncClient(timeout=httpx.Timeout(180)) as client:
        response = await client.get(url)
        response.raise_for_status()
        mime = response.headers.get("Content-Type", "video/mp4")
        return VideoPayload(data=response.content, mime_type=mime)


async def extract_video_payload(output: Any) -> VideoPayload:
    if isinstance(output, dict):
        if isinstance(output.get("video_base64"), str):
            return _decode_base64(output["video_base64"])

        if isinstance(output.get("video_data_uri"), str):
            return _decode_base64(output["video_data_uri"])

        if isinstance(output.get("video_url"), str):
            return await _download_video(output["video_url"])

    if isinstance(output, str):
        if output.startswith("http://") or output.startswith("https://"):
            return await _download_video(output)
        return _decode_base64(output)

    raise ValueError("Unable to extract video from RunPod output")
