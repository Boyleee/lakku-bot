import pytest
from pydantic import ValidationError

from app.schemas import GenerationRequest


def test_generation_request_defaults() -> None:
    request = GenerationRequest(input_image_base64="Zm9v")

    assert request.prompt == "make this image come alive, cinematic motion, smooth animation"
    assert request.duration_seconds == 3.5
    assert request.fps == 16
    assert request.inference_steps == 6
    assert request.video_quality == 6
    assert request.last_image_base64 is None


@pytest.mark.parametrize("fps", [0, 24, 120])
def test_generation_request_rejects_unsupported_fps(fps: int) -> None:
    with pytest.raises(ValidationError):
        GenerationRequest(input_image_base64="Zm9v", fps=fps)


@pytest.mark.parametrize("field,value", [("inference_steps", 31), ("video_quality", 11)])
def test_generation_request_rejects_out_of_range_values(field: str, value: int) -> None:
    with pytest.raises(ValidationError):
        GenerationRequest(input_image_base64="Zm9v", **{field: value})
