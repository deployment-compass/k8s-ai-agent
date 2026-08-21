# Phase 4 — Summary

## Overview

Phase 4 connected the FastAPI application to an LLM. `/api/v1/chat` is now powered by a real model behind a provider-agnostic interface — with no Kubernetes tools yet (that's Phase 5). The default provider is OpenRouter using free models; swapping providers requires only an environment variable change.

---

## What Was Built

### 1. LLM Package — `app/llm/`

New package implementing Ports & Adapters:

| File | Purpose |
|------|---------|
| `base.py` | `BaseLLMClient` ABC, `LLMMessage`, `LLMResponse`, typed exceptions (`LLMAuthError`, `LLMRateLimitError`, `LLMTimeoutError`, `LLMConnectionError`, `LLMProviderError`, `LLMParseError`) |
| `openai_compatible.py` | Single adapter covering every OpenAI-compatible provider via configurable `base_url` + `api_key` + `model`; translates SDK exceptions into our exception types |
| `mock.py` | Deterministic offline client returning valid structured JSON; used for tests and as safe default |
| `factory.py` | `create_llm_client(settings)` with per-provider presets (base URL + default model) for openrouter, groq, gemini, ollama, openai |
| `parsing.py` | Tolerant JSON extraction (handles markdown fences and surrounding prose) + Pydantic schema validation |
| `prompts.py` | System prompt: Kubernetes ops assistant persona, explicit "no cluster access yet" clause, strict JSON output schema |

### 2. Chat Service Rewrite — `app/services/chat_service.py`

Replaced the echo stub with real orchestration:

```text
system prompt + user message
        ↓
   LLM call
        ↓
parse + validate against ChatResponse
        ↓
 ┌──────┴───────┐
Valid         Invalid
 │               │
 ▼               ▼
Return      One corrective retry
            ("your reply was not valid JSON, try again")
                │
           ┌────┴────┐
          Valid    Invalid
           │         │
           ▼         ▼
         Return   LLMParseError → HTTP 502
```

The client is cached at module level (`get_llm_client()` / `set_llm_client()`) so tests can inject mocks.

### 3. Structured Response — `app/schemas/chat.py`

```python
class ChatResponse(BaseModel):
    answer: str                      # what the user reads
    reasoning_summary: str           # seed of audit log field (Phase 10)
    suggested_next_steps: list[str]  # nudges toward diagnostic workflow (Phase 5/6)
```

`ChatRequest.message` now enforces `min_length=1` (empty message → 422).

### 4. Error Mapping — `app/api/v1/chat.py`

| Provider failure | HTTP response |
|------------------|---------------|
| Auth failure | 500 (config problem) |
| Rate limited | 429 + `Retry-After` header when provided |
| Timeout | 504 |
| Connection / provider 5xx / parse failure | 502 |

API keys never appear in error responses or logs.

### 5. Configuration

Seven new settings in `app/config.py`: `llm_provider` (default `mock`), `llm_api_key`, `llm_base_url`, `llm_model`, `llm_timeout_seconds`, `llm_temperature`, `llm_max_retries`. Explicit env vars override provider presets. `.env.example` documents OpenRouter setup.

### 6. Dependency

Added `openai>=1.50.0` (installed 3.3.1) — used only inside the adapter, never imported above the `app/llm/` boundary.

---

## Verification

### Test Suite

13 tests → **37 tests**, all passing:

- `test_llm_factory.py` (8): mock selection, all 5 provider presets, explicit base_url/model override, unknown provider rejection
- `test_llm_parsing.py` (9): plain JSON, markdown fences, surrounding prose, no JSON, invalid JSON, non-object JSON, validation success/failure/coercion
- `test_chat_service.py` (4): success path, retry-on-invalid-JSON path (asserts corrective message roles `[system, user, assistant, user]`), failure after retry, system prompt inclusion
- `test_chat.py` (6): structured endpoint response, empty message → 422, missing field → 422, rate limit → 429 with `Retry-After`, timeout → 504, auth error → 500
- Existing health (1) and Kubernetes (9) tests untouched and green

### Live Smoke Test

Server started with `LLM_PROVIDER=mock`:

```json
POST /api/v1/chat {"message": "What does CrashLoopBackOff mean?"}

{
  "answer": "Mock answer to: What does CrashLoopBackOff mean?",
  "reasoning_summary": "Mock reasoning: identified the question and produced a canned answer.",
  "suggested_next_steps": [
    "Inspect pods with GET /clusters/default/namespaces/{namespace}/pods",
    "Check events with GET /clusters/default/namespaces/{namespace}/events"
  ]
}
```

**Not yet verified:** a real OpenRouter call — no API key was configured during this phase. Add `LLM_API_KEY` to `.env` and send one request to complete M4.10.

---

## Architecture

```text
                     HTTP
                      │
                      ▼
               ┌─────────────┐
               │   FastAPI   │
               │  /api/v1/…  │
               └──────┬──────┘
                      │
                      ▼
               ┌─────────────┐
               │ ChatService │
               └──────┬──────┘
                      │
                      ▼
              ┌───────────────┐
              │ BaseLLMClient │
              └───────┬───────┘
           ┌──────────┼──────────┐
           ▼          ▼          ▼
   OpenAICompatible  Mock    (future adapters)
        Client       Client
           │
           ▼
     openai SDK
           │
           ▼
   OpenRouter (default) / Groq / Gemini / Ollama
```

---

## Key Decisions

| Decision | Choice | Reason |
|----------|--------|--------|
| Provider abstraction | One OpenAI-compatible adapter | All target providers speak the same protocol; per-provider adapters would be near-duplicate code |
| Default provider | OpenRouter free models | Free tier, strong models (`deepseek/deepseek-r1:free`) |
| Structured output | Prompt-based JSON + Pydantic validation + retry | Works on free models without native JSON mode; correctness before optimization |
| Conversation scope | Single-turn | Matches current schema; history arrives with AgentState (Phase 6) |
| Streaming | Deferred | Plain JSON now; SSE can be added later without breaking changes |
| Mock client as default | `LLM_PROVIDER=mock` | App works offline out of the box; zero cost, zero rate limits |

---

## Files Created

| File | Purpose |
|------|---------|
| `app/llm/__init__.py` | Package exports |
| `app/llm/base.py` | Interface, message/response types, exceptions |
| `app/llm/openai_compatible.py` | Universal OpenAI-compatible adapter |
| `app/llm/mock.py` | Deterministic offline client |
| `app/llm/factory.py` | Provider presets + selection |
| `app/llm/parsing.py` | JSON extraction + validation |
| `app/llm/prompts.py` | System prompt |
| `tests/test_llm_factory.py` | Factory tests |
| `tests/test_llm_parsing.py` | Parsing tests |
| `tests/test_chat_service.py` | Service orchestration tests |

## Files Modified

| File | Change |
|------|--------|
| `pyproject.toml` | Added `openai` dependency |
| `app/config.py` | Added 7 `llm_*` settings |
| `.env.example` | Documented LLM configuration |
| `app/schemas/chat.py` | Structured `ChatResponse`, `min_length=1` on request |
| `app/services/chat_service.py` | Replaced echo stub with LLM orchestration |
| `app/api/v1/chat.py` | Added exception → HTTP status mapping |
| `tests/test_chat.py` | Updated for new schema + error mapping tests |
| `README.md` | Phase 4 status, structure, chat docs, config table |
| `plan/phase-4/phase-4.md` | Implementation plan (written before coding) |

---

## How to Use

```bash
# Offline (default, no key needed)
uv run uvicorn app.main:app --reload

# With a free OpenRouter model
cp .env.example .env
# edit .env: set LLM_API_KEY=<key from openrouter.ai>
uv run uvicorn app.main:app --reload

curl -X POST http://localhost:8000/api/v1/chat \
  -H "Content-Type: application/json" \
  -d '{"message": "What does CrashLoopBackOff mean?"}'
```

Free model IDs rotate monthly on OpenRouter — if the configured model disappears, pick another from `openrouter.ai/models` with the `:free` filter and update `LLM_MODEL`.

---

## What Comes Next (Phase 5)

Tool calling: wire `KubernetesClient.get_pods/get_deployment/get_service/get_pod_logs/get_events` into the LLM as callable tools. The interface built here stays unchanged — tools slot in between `ChatService` and the model.
