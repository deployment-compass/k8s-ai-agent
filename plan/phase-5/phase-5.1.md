# Phase 5.1 — Agent Activity Logging

## 1. Objective

Make the agent's behavior visible during operation. After Phase 5, a single chat
request can trigger up to 9 LLM round-trips and multiple Kubernetes tool calls —
all invisible unless something fails. Phase 5.1 adds operational console logging,
controlled by environment variables.

This is **operational logging** (what is the agent doing right now?).
Structured audit persistence remains Phase 10.

---

# 2. Decisions made

| Decision | Choice | Reason |
| --- | --- | --- |
| Default state | Enabled | Development visibility out of the box |
| Destination | Console only (stdlib `logging`) | Simple; file/structured persistence belongs to Phase 10 |
| Control model | Toggle + level | `AGENT_LOG_ENABLED` on/off, `AGENT_LOG_LEVEL` for detail |

---

# 3. Configuration

Two new settings in `app/config.py`:

```python
agent_log_enabled: bool = True     # AGENT_LOG_ENABLED
agent_log_level: str = "INFO"      # AGENT_LOG_LEVEL  (INFO | DEBUG | WARNING ...)
```

Disabled does not mean silent: the `app.*` logger hierarchy drops to `ERROR`,
so failures still surface while activity chatter stops.

---

# 4. Setup — `app/logging_setup.py`

New module with a single function, called from the existing lifespan in `main.py`:

```text
configure_logging(settings)
    enabled  → basicConfig(format="%(asctime)s %(levelname)s %(name)s %(message)s")
               app logger level ← AGENT_LOG_LEVEL
    disabled → app logger level ← ERROR
```

Idempotent: safe to call once at startup; tests can re-call with different settings.

---

# 5. What gets logged

| Location | Level | Content |
| --- | --- | --- |
| `chat_service.handle_chat` | INFO | Request received (message truncated to ~100 chars) |
| `AgentLoop.run` | INFO | Start: mode, iteration budget |
| `AgentLoop.run` | INFO | Complete: rounds used, tool calls made, total duration |
| `AgentLoop.run` | WARNING | Mode downgrades (provider rejected tools / unparseable first response) |
| `ToolRegistry.execute` | INFO | Each tool call: name + arguments; result status (ok/error), size, duration |
| `ToolRegistry.execute` | DEBUG | First ~200 chars of the tool result |
| `OpenAICompatibleClient.complete` | DEBUG | Model, message/tool counts, latency, token usage, finish reason |

## Security rules

- Never log API keys or request headers.
- Tool results appear only as short previews (pod logs can contain secrets).
- User messages are truncated before logging.
- Error logs include exception types and status codes, never payloads verbatim.

---

# 6. Testing strategy

New `tests/test_logging.py` using pytest's `caplog`:

- INFO run shows tool calls with arguments but no result bodies
- DEBUG adds result previews and LLM timing lines
- disabled → zero INFO records from `app.*` loggers
- settings parse `AGENT_LOG_ENABLED=false` and `AGENT_LOG_LEVEL=DEBUG`
- all 54 existing tests stay green

---

# 7. Milestones

| Milestone | Goal |
| --------- | ---- |
| **M5.1.1** | Settings + `.env.example` |
| **M5.1.2** | `logging_setup.py` + lifespan wiring |
| **M5.1.3** | Instrument loop, registry, adapter, service |
| **M5.1.4** | Tests + README documentation |

---

# 8. What we explicitly DON'T do

### No file output

Console only. File rotation/structured JSON comes with observability work (Phase 14) and audit logging (Phase 10).

### No audit trail

This log is for humans watching a terminal. The tamper-evident record of
requests/tools/approvals/results is Phase 10's database-backed audit log.

### No log correlation IDs yet

Single-request correlation arrives naturally with AgentState (Phase 6);
request IDs will be introduced there rather than bolted on here.
