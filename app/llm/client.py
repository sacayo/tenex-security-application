"""OpenAI-compatible chat-completions client for the vLLM server on Modal.

Deliberately small and synchronous: one `POST /chat/completions`, one
retry policy, one parsing path. Everything model-specific is here:

- Modal proxy auth: `Authorization: Bearer <token>`. That header is consumed
  by Modal's proxy, so the vLLM server behind it must NOT also run with
  `--api-key` or the two would collide.
- Nemotron 3.5 Lightning reasons by default; we turn it off per request via
  `chat_template_kwargs.enable_thinking=false`. A five-sentence summary of
  pre-computed facts has nothing to reason about, and disabling it keeps
  latency low and removes any interaction with structured output.
- Structured output via `response_format: json_schema`. If the server
  rejects/ignores it and we get unparseable text, retry once without it and
  extract the first balanced JSON object.
- Cold starts: Modal holds the connection while a scale-to-zero container
  boots, so a cold start looks like a slow response. The generous read
  timeout is what absorbs it; a read timeout is therefore terminal (a second
  full wait would overrun the UI's poll window). Connection resets and 5xx
  are retried once.
"""

from __future__ import annotations

import json
import logging
import time
from dataclasses import dataclass
from functools import lru_cache
from typing import Any, Protocol

import httpx

from app.config import get_settings
from app.service.narrative import strip_thinking

logger = logging.getLogger(__name__)

CONNECT_TIMEOUT_SECONDS = 30.0
RETRY_DELAY_SECONDS = 2.0
MAX_TOKENS = 800
TEMPERATURE = 0.2


class LlmError(Exception):
    """Base class for anything the model call can raise."""


class LlmUnavailable(LlmError):
    """Could not get a response: connect failure, timeout, or repeated 5xx."""


class LlmTruncated(LlmError):
    """Server stopped at max_tokens before finishing the JSON."""


class LlmBadResponse(LlmError):
    """Got a 2xx but the body was not a usable completion."""


@dataclass(frozen=True)
class LlmCompletion:
    data: dict[str, Any]
    model: str
    latency_ms: int


class NarrativeClient(Protocol):
    """What `app.llm.generate` needs. Tests substitute a fake."""

    model: str

    def complete(
        self, *, system_prompt: str, user_prompt: str, json_schema: dict[str, Any]
    ) -> LlmCompletion: ...


class OpenAICompatibleClient:
    def __init__(
        self,
        *,
        base_url: str,
        api_key: str,
        model: str,
        timeout_seconds: float,
        transport: httpx.BaseTransport | None = None,
    ) -> None:
        self.model = model
        self._url = base_url.rstrip("/") + "/chat/completions"
        headers = {"Content-Type": "application/json"}
        if api_key:
            headers["Authorization"] = f"Bearer {api_key}"
        self._http = httpx.Client(
            headers=headers,
            timeout=httpx.Timeout(timeout_seconds, connect=CONNECT_TIMEOUT_SECONDS),
            transport=transport,
        )

    # -- request building ---------------------------------------------------

    def _body(
        self,
        system_prompt: str,
        user_prompt: str,
        json_schema: dict[str, Any] | None,
    ) -> dict[str, Any]:
        body: dict[str, Any] = {
            "model": self.model,
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
            "temperature": TEMPERATURE,
            "max_tokens": MAX_TOKENS,
            # Nemotron-specific: reasoning is on by default; turn it off.
            "chat_template_kwargs": {"enable_thinking": False},
        }
        if json_schema is not None:
            body["response_format"] = {
                "type": "json_schema",
                "json_schema": {"name": "narrative", "schema": json_schema},
            }
        return body

    # -- transport ----------------------------------------------------------

    def _post(self, body: dict[str, Any]) -> dict[str, Any]:
        """POST once, retrying a single time on reset / 5xx only."""
        last_error: Exception | None = None
        for attempt in (1, 2):
            try:
                response = self._http.post(self._url, json=body)
            except (
                httpx.ConnectError,
                httpx.RemoteProtocolError,
                httpx.ConnectTimeout,
            ) as exc:
                last_error = LlmUnavailable(
                    f"could not reach the model server ({exc.__class__.__name__})"
                )
                logger.warning("llm connect failure attempt=%d: %s", attempt, exc)
            except httpx.ReadTimeout as exc:
                # Terminal on purpose: we already waited the full budget.
                raise LlmUnavailable(
                    "model did not respond within the timeout (cold start?)"
                ) from exc
            except httpx.HTTPError as exc:
                raise LlmUnavailable(f"transport error: {exc}") from exc
            else:
                if response.status_code >= 500:
                    last_error = LlmUnavailable(
                        f"server error {response.status_code}: {response.text[:200]}"
                    )
                    logger.warning(
                        "llm 5xx attempt=%d status=%d", attempt, response.status_code
                    )
                elif response.status_code in (401, 403):
                    raise LlmError(
                        f"authentication rejected ({response.status_code}); check LLM_API_KEY "
                        "and make sure the server does not also set --api-key"
                    )
                elif response.status_code >= 400:
                    raise LlmBadResponse(
                        f"request rejected {response.status_code}: {response.text[:300]}"
                    )
                else:
                    try:
                        return response.json()
                    except ValueError as exc:
                        raise LlmBadResponse("non-JSON body from server") from exc
            if attempt == 1:
                time.sleep(RETRY_DELAY_SECONDS)
        raise LlmUnavailable(str(last_error)) from last_error

    # -- response parsing ---------------------------------------------------

    @staticmethod
    def _extract_content(payload: dict[str, Any]) -> tuple[str, str | None]:
        try:
            choice = payload["choices"][0]
            message = choice["message"]
        except (KeyError, IndexError, TypeError) as exc:
            raise LlmBadResponse("response has no choices[0].message") from exc
        if reasoning := message.get("reasoning_content") or message.get("reasoning"):
            logger.debug(
                "llm returned reasoning (%d chars) despite enable_thinking=false",
                len(reasoning),
            )
        content = message.get("content")
        if not isinstance(content, str):
            raise LlmBadResponse("choices[0].message.content is not a string")
        return content, choice.get("finish_reason")

    @staticmethod
    def _first_json_object(text: str) -> dict[str, Any] | None:
        """Return the first balanced {...} that parses as a JSON object."""
        depth = 0
        start = -1
        in_string = False
        escape = False
        for index, char in enumerate(text):
            if in_string:
                if escape:
                    escape = False
                elif char == "\\":
                    escape = True
                elif char == '"':
                    in_string = False
                continue
            if char == '"':
                in_string = True
            elif char == "{":
                if depth == 0:
                    start = index
                depth += 1
            elif char == "}" and depth > 0:
                depth -= 1
                if depth == 0 and start >= 0:
                    try:
                        parsed = json.loads(text[start : index + 1])
                    except ValueError:
                        start = -1
                        continue
                    if isinstance(parsed, dict):
                        return parsed
                    start = -1
        return None

    def _parse(self, payload: dict[str, Any]) -> dict[str, Any] | None:
        content, finish_reason = self._extract_content(payload)
        if finish_reason == "length":
            raise LlmTruncated(f"output hit max_tokens={MAX_TOKENS} before completing")
        content = strip_thinking(content).strip()
        try:
            parsed = json.loads(content)
        except ValueError:
            parsed = self._first_json_object(content)
        if isinstance(parsed, dict):
            return parsed
        return None

    # -- public -------------------------------------------------------------

    def complete(
        self, *, system_prompt: str, user_prompt: str, json_schema: dict[str, Any]
    ) -> LlmCompletion:
        started = time.perf_counter()

        payload = self._post(self._body(system_prompt, user_prompt, json_schema))
        data = self._parse(payload)
        if data is None:
            # Structured output either ignored or produced garbage; one plain retry.
            logger.warning(
                "llm output unparseable with json_schema; retrying without it"
            )
            payload = self._post(self._body(system_prompt, user_prompt, None))
            data = self._parse(payload)
        if data is None:
            raise LlmBadResponse("model output was not a JSON object")

        latency_ms = int((time.perf_counter() - started) * 1000)
        model = payload.get("model") or self.model
        logger.info("llm completion ok model=%s latency=%dms", model, latency_ms)
        return LlmCompletion(data=data, model=str(model), latency_ms=latency_ms)


# --------------------------------------------------------------------------
# FastAPI dependency
# --------------------------------------------------------------------------


@lru_cache
def _cached_client() -> OpenAICompatibleClient:
    settings = get_settings()
    return OpenAICompatibleClient(
        base_url=settings.llm_base_url,
        api_key=settings.llm_api_key,
        model=settings.llm_model,
        timeout_seconds=settings.llm_timeout_seconds,
    )


def get_llm_client() -> NarrativeClient | None:
    """Return the configured client, or None when the feature is off.

    Routes turn None into a 503 so the frontend can hide the card. Tests
    override this dependency with a fake.
    """
    settings = get_settings()
    if not settings.llm_enabled or not settings.llm_base_url:
        return None
    return _cached_client()
