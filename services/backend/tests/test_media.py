import asyncio
import base64

import pytest

from app.media import extract_video_payload


@pytest.mark.parametrize(
    "value",
    [
        base64.b64encode(b"video").decode("utf-8"),
        "data:video/mp4;base64," + base64.b64encode(b"video").decode("utf-8"),
    ],
)
def test_extract_video_payload_from_base64(value: str) -> None:
    payload = asyncio.run(extract_video_payload({"video_base64": value}))
    assert payload.data == b"video"
    assert payload.mime_type.startswith("video/")


def test_extract_video_payload_invalid_type() -> None:
    with pytest.raises(ValueError):
        asyncio.run(extract_video_payload(123))
