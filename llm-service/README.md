# LLM service: Nemotron 3.5 Lightning on Modal

The narrative layer (spec.md §7.1) calls an OpenAI-compatible vLLM server
that runs on Modal, because Railway has no GPUs. This directory documents
the contract the backend is written against; the Modal deployment itself is
managed outside this repo.

## Contract

| Item | Value |
|---|---|
| Base URL | `https://<workspace>--<app>-serve.modal.run/v1` → `LLM_BASE_URL` |
| Auth | Modal **proxy auth**, single combined credential: `Authorization: Bearer <token>` → `LLM_API_KEY` |
| Model id in requests | whatever `--served-model-name` is (default `nvidia/NVIDIA-Nemotron-3.5-Lightning-30B-A3B-BF16`; `-NVFP4` also fine) → `LLM_MODEL` |
| Endpoint used | `POST {base}/chat/completions` only |
| Thinking | disabled per request via `chat_template_kwargs: {"enable_thinking": false}` |
| Structured output | `response_format: {"type": "json_schema", ...}` |

Modal's proxy consumes the `Authorization` header. The vLLM process behind
it must therefore **not** run with `--api-key`; if it does, every request
fails `401` and the backend logs a hint to that effect.

## Model

`nvidia/NVIDIA-Nemotron-3.5-Lightning-30B-A3B` — 30B total / 3B active,
hybrid Mamba-2 + MoE + attention, fits one H100/A100 80GB. Reasoning is on
by default and switchable via the chat template; the backend always turns it
off (nothing to reason about when summarising pre-computed facts; keeps
latency and tokens minimal; no interaction with guided decoding).

NVIDIA's reference single-GPU serve command (the reasoning parser is
nice-to-have here since thinking is disabled, but harmless):

```bash
export MODEL_CKPT=nvidia/NVIDIA-Nemotron-3.5-Lightning-30B-A3B-BF16
vllm serve --model $MODEL_CKPT --served-model-name $MODEL_CKPT \
  --max-num-seqs 128 --enable-prefix-caching --async-scheduling \
  --mamba-backend flashinfer --mamba-ssm-cache-dtype float16 \
  --enable-mamba-cache-stochastic-rounding --mamba-cache-philox-rounds 5 \
  --reasoning-parser nemotron_v3 \
  --tool-call-parser qwen3_coder --enable-auto-tool-choice
```

Do **not** add `--api-key` (see above).

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

- `.model` equals `$LLM_MODEL` (otherwise fix `LLM_MODEL` / `--served-model-name`);
- `finish_reason` is `"stop"`;
- `content` is `{"ok": true}` with **no** `<think>` marker;
- the first call after idle may take a minute or two (cold start) — that is
  the scale-to-zero container booting, and the backend's 300 s timeout is
  sized for it.

Failure modes:

| Symptom | Likely cause |
|---|---|
| `401` | wrong token, or vLLM also has `--api-key` set |
| `404` on the URL | missing `/v1` in `LLM_BASE_URL` |
| `400` mentioning the model | `LLM_MODEL` does not match `--served-model-name` |
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

Any OpenAI-compatible server works (`vllm serve` on a local GPU, or a stub).
Point `LLM_BASE_URL` at it and set `LLM_API_KEY` to whatever it expects (or
leave empty — the header is omitted when blank).
