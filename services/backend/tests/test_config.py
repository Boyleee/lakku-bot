from app.config import _normalize_runpod_api_key, _normalize_runpod_endpoint_id


def test_normalize_runpod_api_key_supports_bearer_prefix() -> None:
    assert _normalize_runpod_api_key("Bearer abc123") == "abc123"
    assert _normalize_runpod_api_key(" abc123 ") == "abc123"


def test_normalize_runpod_endpoint_id_supports_url() -> None:
    assert _normalize_runpod_endpoint_id("kkj2zia52acp5k") == "kkj2zia52acp5k"
    assert (
        _normalize_runpod_endpoint_id("https://api.runpod.ai/v2/kkj2zia52acp5k/run")
        == "kkj2zia52acp5k"
    )
    assert _normalize_runpod_endpoint_id("/v2/kkj2zia52acp5k/status/abc") == "kkj2zia52acp5k"
