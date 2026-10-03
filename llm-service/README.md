# LLM service: Nemotron 3.5 Lightning on Modal

The narrative layer (spec.md §7.1) calls a dedicated OpenAI-compatible
inference endpoint hosted on Modal, because Railway has no GPUs. This
directory documents the request contract the backend is written against; how
the endpoint is provisioned is managed outside this repo.

## Contract

| Item | Value |
|---|---|
| Base URL | `https://<workspace>--<app>-serve.modal.run/v1` → `LLM_BASE_URL` |
| Auth | Modal **proxy auth**, single combined credential: `Authorization: Bearer <token>` → `LLM_API_KEY` |
| Model id in requests | the id the endpoint serves (default `nvidia/NVIDIA-Nemotron-3.5-Lightning-30B-A3B-BF16`) → `LLM_MODEL` |
| Endpoint used | `POST {base}/chat/completions` only |
| Thinking | disabled per request via `chat_template_kwargs: {"enable_thinking": false}` |
| Structured output | `response_format: {"type": "json_schema", ...}` |

Modal's proxy consumes the `Authorization` header; the backend sends the
Modal proxy token as `LLM_API_KEY`.

## Model

`nvidia/NVIDIA-Nemotron-3.5-Lightning-30B-A3B` — 30B total / 3B active,
hybrid Mamba-2 + MoE + attention. Reasoning is on by default and switchable
via the chat template; the backend always turns it off (nothing to reason
about when summarising pre-computed facts; keeps latency and tokens minimal;
no interaction with structured output).

The endpoint is provisioned on Modal; its serving configuration is out of
scope for this repo.

## Smoke test (run before wiring the backend)

```bash
export LLM_BASE_URL='https://<workspace>--<app>-serve.modal.run/v1'
export LLM_API_KEY='<modal proxy token>'
export LLM_MODEL='nvidia/NVIDIA-Nemotron-3.5-Lightning-30B-A3B-BF16'

curl -sS "$LLM_BASE_URL/chat/completions" \
  -H "Authorization: Bearer $LLM_API_KEY" \
  -H 'Content-Type: application/json' \
  -d '{
    "model": "'"$LLM_MODEL"'",
    "max_tokens": 200,
    "temperature": 0.2,
    "messages": [{"role": "user", "content": "Reply with the JSON {\"ok\": true} and nothing else."}],
    "chat_template_kwargs": {"enable_thinking": false},
    "response_format": {"type": "json_schema", "json_schema": {"name": "t", "schema": {"type": "object", "properties": {"ok": {"type": "boolean"}}, "required": ["ok"]}}}
  }' | jq '.model, .choices[0].finish_reason, .choices[0].message.content'
```

Expected:

- `.model` equals `$LLM_MODEL` (otherwise fix `LLM_MODEL`);
- `finish_reason` is `"stop"`;
- `content` is `{"ok": true}` with **no** `<think>` marker;
- the first call after idle may take a minute or two (cold start) — that is
  the scale-to-zero container booting, and the backend's 300 s timeout is
  sized for it.

Failure modes:

| Symptom | Likely cause |
|---|---|
| `401` | wrong or missing token, or proxy-auth mismatch |
| `404` on the URL | missing `/v1` in `LLM_BASE_URL` |
| `400` mentioning the model | `LLM_MODEL` does not match the id the endpoint serves |
| `content` starts with `<think>` | server ignored `enable_thinking`; the backend strips it, but check the chat template |

## Wiring the backend (Railway)

Set on the API service:

```
LLM_ENABLED=true
LLM_BASE_URL=https://<workspace>--<app>-serve.modal.run/v1
LLM_API_KEY=<modal proxy token>
LLM_MODEL=nvidia/NVIDIA-Nemotron-3.5-Lightning-30B-A3B-BF16
LLM_TIMEOUT_SECONDS=300
LLM_REFRESH_COOLDOWN_SECONDS=300
```

With `LLM_ENABLED=false` (the default) the API behaves exactly as before and
the dashboard hides the summary card.

## Local development without Modal

Any OpenAI-compatible server works (a local server or a stub).
Point `LLM_BASE_URL` at it and set `LLM_API_KEY` to whatever it expects (or
leave empty — the header is omitted when blank).
