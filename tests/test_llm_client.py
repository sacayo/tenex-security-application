"""Tests for app/llm/client.py using httpx.MockTransport - no network."""

import json

import httpx
import pytest

from app.llm import client as client_module
from app.llm.client import (
    LlmBadResponse,
    LlmError,
    LlmTruncated,
    LlmUnavailable,
    OpenAICompatibleClient,
)

SCHEMA = {"type": "object", "properties": {"a": {"type": "integer"}}}
GOOD_JSON = '{"headline": "ok", "a": 1}'


def _completion(content: str, finish_reason: str = "stop", **extra) -> dict:
    message = {"role": "assistant", "content": content, **extra}
    return {
        "model": "served-name",
        "choices": [{"index": 0, "message": message, "finish_reason": finish_reason}],
    }


def _make(handler, **kwargs) -> OpenAICompatibleClient:
    return OpenAICompatibleClient(
        base_url="http://llm.test/v1/",
        api_key="secret-token",
        model="configured-name",
        timeout_seconds=5,
        transport=httpx.MockTransport(handler),
        **kwargs,
    )


@pytest.fixture(autouse=True)
def _no_retry_sleep(monkeypatch) -> None:
    monkeypatch.setattr(client_module, "RETRY_DELAY_SECONDS", 0)


def test_request_shape_and_auth() -> None:
    seen: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        seen.append(request)
        return httpx.Response(200, json=_completion(GOOD_JSON))

    result = _make(handler).complete(
        system_prompt="sys", user_prompt="facts", json_schema=SCHEMA
    )

    assert len(seen) == 1
    request = seen[0]
    assert str(request.url) == "http://llm.test/v1/chat/completions"
    assert request.headers["Authorization"] == "Bearer secret-token"
    body = json.loads(request.content)
    assert body["model"] == "configured-name"
    assert body["chat_template_kwargs"] == {"enable_thinking": False}
    assert body["response_format"]["type"] == "json_schema"
    assert body["response_format"]["json_schema"]["schema"] == SCHEMA
    assert body["messages"][0] == {"role": "system", "content": "sys"}
    assert body["messages"][1] == {"role": "user", "content": "facts"}
    assert "reasoning_effort" not in body

    assert result.data == {"headline": "ok", "a": 1}
    assert result.model == "served-name"
    assert result.latency_ms >= 0


def test_truncated_output_raises_distinct_error() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json=_completion('{"headline": "cut', "length"))

    with pytest.raises(LlmTruncated):
        _make(handler).complete(system_prompt="s", user_prompt="u", json_schema=SCHEMA)


def test_leaked_think_block_is_stripped() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200, json=_completion("<think>reasoning...</think>\n" + GOOD_JSON)
        )

    result = _make(handler).complete(
        system_prompt="s", user_prompt="u", json_schema=SCHEMA
    )
    assert result.data["a"] == 1


def test_unparseable_output_retries_without_schema_and_extracts_object() -> None:
    bodies: list[dict] = []

    def handler(request: httpx.Request) -> httpx.Response:
        body = json.loads(request.content)
        bodies.append(body)
        if len(bodies) == 1:
            return httpx.Response(200, json=_completion("not json at all"))
        return httpx.Response(
            200, json=_completion('Sure! Here it is: {"a": 2, "s": "x}"} done.')
        )

    result = _make(handler).complete(
        system_prompt="s", user_prompt="u", json_schema=SCHEMA
    )
    assert len(bodies) == 2
    assert "response_format" in bodies[0]
    assert "response_format" not in bodies[1]
    assert result.data == {"a": 2, "s": "x}"}


def test_unparseable_twice_raises_bad_response() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json=_completion("still prose"))

    with pytest.raises(LlmBadResponse):
        _make(handler).complete(system_prompt="s", user_prompt="u", json_schema=SCHEMA)


def test_5xx_is_retried_once_then_succeeds() -> None:
    calls = {"n": 0}

    def handler(request: httpx.Request) -> httpx.Response:
        calls["n"] += 1
        if calls["n"] == 1:
            return httpx.Response(503, text="booting")
        return httpx.Response(200, json=_completion(GOOD_JSON))

    result = _make(handler).complete(
        system_prompt="s", user_prompt="u", json_schema=SCHEMA
    )
    assert calls["n"] == 2
    assert result.data["a"] == 1


def test_persistent_5xx_raises_unavailable() -> None:
    calls = {"n": 0}

    def handler(request: httpx.Request) -> httpx.Response:
        calls["n"] += 1
        return httpx.Response(502, text="bad gateway")

    with pytest.raises(LlmUnavailable):
        _make(handler).complete(system_prompt="s", user_prompt="u", json_schema=SCHEMA)
    assert calls["n"] == 2


def test_read_timeout_is_terminal_not_retried() -> None:
    calls = {"n": 0}

    def handler(request: httpx.Request) -> httpx.Response:
        calls["n"] += 1
        raise httpx.ReadTimeout("slow model")

    with pytest.raises(LlmUnavailable, match="timeout"):
        _make(handler).complete(system_prompt="s", user_prompt="u", json_schema=SCHEMA)
    assert calls["n"] == 1


def test_connect_error_is_retried_once() -> None:
    calls = {"n": 0}

    def handler(request: httpx.Request) -> httpx.Response:
        calls["n"] += 1
        raise httpx.ConnectError("refused")

    with pytest.raises(LlmUnavailable):
        _make(handler).complete(system_prompt="s", user_prompt="u", json_schema=SCHEMA)
    assert calls["n"] == 2


def test_401_explains_proxy_auth_collision() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(401, text="unauthorized")

    with pytest.raises(LlmError, match="authentication rejected"):
        _make(handler).complete(system_prompt="s", user_prompt="u", json_schema=SCHEMA)


def test_no_api_key_sends_no_authorization_header() -> None:
    seen: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        seen.append(request)
        return httpx.Response(200, json=_completion(GOOD_JSON))

    OpenAICompatibleClient(
        base_url="http://llm.test/v1",
        api_key="",
        model="m",
        timeout_seconds=5,
        transport=httpx.MockTransport(handler),
    ).complete(system_prompt="s", user_prompt="u", json_schema=SCHEMA)
    assert "Authorization" not in seen[0].headers
