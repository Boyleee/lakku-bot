import pytest
import httpx

from app.runpod_client import RunPodClient, RunPodError


@pytest.mark.parametrize(
    ("status_code", "expected_fragment"),
    [
        (403, "RUNPOD_API_KEY"),
        (404, "RUNPOD_ENDPOINT_ID"),
        (500, "Проверьте логи RunPod endpoint"),
    ],
)
def test_raise_for_status_with_hint(status_code: int, expected_fragment: str) -> None:
    request = httpx.Request("POST", "https://api.runpod.ai/v2/abc/run")
    response = httpx.Response(status_code=status_code, request=request, text="boom")

    with pytest.raises(RunPodError) as exc:
        RunPodClient._raise_for_status_with_hint(response, path="run")

    assert expected_fragment in str(exc.value)
