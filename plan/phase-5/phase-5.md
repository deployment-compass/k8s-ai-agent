# Phase 5 — Tool Calling

## 1. Phase objective

At the end of Phase 5, you should be able to do this:

```text
HTTP Request
     │
     ▼
  FastAPI
     │
     ▼
 ChatService ──► Agent Loop
                     │
                     ▼
              LLM (tools attached)
                     │
             ┌───────┴────────┐
             ▼                ▼
        tool_calls?       final text
             │                │
             ▼                ▼
      Validate args      Parse structured
      (DNS-1123 regex,   JSON → ChatResponse
       default ns)            + tools_used
             │
             ▼
       KubernetesClient   ← existing, unchanged
             │
             ▼
       Truncate result
             │
             └──► feed back as tool message, repeat
```

For example:

```http
POST /api/v1/chat
{ "message": "Why is the backend broken?" }
```

and the agent inspects the real cluster — deployments → pods → events → logs — before answering with an evidence-based diagnosis.

This is the milestone where the project becomes an actual agent:
**natural language → tool selection → real cluster inspection → diagnosis.**

---

# 2. Decisions already made

| Decision | Choice | Reason |
| --- | --- | --- |
| Tool mechanism | Native function calling **with prompted fallback** | Native is most reliable; fallback keeps models without tool support (e.g. `deepseek-r1:free`) usable |
| Tool set | All 7 `KubernetesClient` read methods | More diagnostic power; all are safe reads under RBAC |
| Namespace resolution | Configurable `DEFAULT_NAMESPACE` | Tool args fall back to it when omitted |
| Transparency | `tools_used` added to `ChatResponse` | Users see what was inspected; seeds audit logging (Phase 10) |

---

# 3. Interface extension — `app/llm/base.py`

Backward compatible additions:

```python
@dataclass(frozen=True)
class ToolCall:
    id: str
    name: str
    arguments: dict          # parsed JSON args

@dataclass(frozen=True)
class LLMMessage:
    role: str                          # system | user | assistant | tool
    content: str | None                # nullable when tool_calls present
    tool_calls: tuple[ToolCall, ...] = ()   # assistant messages
    tool_call_id: str | None = None         # tool-role messages
    name: str | None = None                 # tool name on tool-role messages

@dataclass(frozen=True)
class LLMResponse:
    content: str | None
    tool_calls: tuple[ToolCall, ...] = ()
    ...
```

`BaseLLMClient.complete(messages, tools=None)` — omitting tools reproduces exact Phase 4 behavior.

Why richer messages: OpenAI-style history requires echoing back the assistant's tool-call message plus one `tool` role message per result. The adapter owns the wire format; our types stay provider-neutral.

---

# 4. Tool registry — `app/agent/tools.py`

All seven read operations exposed as tools:

| Tool | Parameters | Source method |
| --- | --- | --- |
| `get_pods` | namespace | `get_pods` |
| `get_deployments` | namespace | `get_deployments` |
| `get_deployment` | namespace, name | `get_deployment` |
| `get_services` | namespace | `get_services` |
| `get_service` | namespace, name | `get_service` |
| `get_pod_logs` | namespace, pod_name | `get_pod_logs` |
| `get_events` | namespace | `get_events` |

Each definition carries: name, description (LLM-facing), JSON schema for parameters, handler.

### The safe executor

Every tool call passes through one executor function that applies, in order:

```text
validate arguments        DNS-1123 regex on names; unknown tool → error result
        ↓
apply defaults            missing namespace → settings.default_namespace
        ↓
execute                   KubernetesClient call
        ↓
capture errors            ApiException → {"error": "..."} as RESULT, not exception
        ↓
truncate                  logs → tail ~8000 chars; lists/events capped
```

Two deliberate behaviors:

1. **Errors are reasoning material.** A 403 RBAC denial or 404 becomes `{"error": ...}` fed back to the model, which can adapt (try another namespace, explain the limitation). The request does not fail.
2. **Truncation protects the context window.** Pod logs and event lists can be enormous; caps keep the loop bounded.

---

# 5. Dual-strategy loop — `app/agent/loop.py`

## Native strategy

Tools sent via the API's `tools` parameter; model emits native `tool_calls`.

## Prompted fallback strategy

Tool catalog injected into the system prompt; model replies with plain JSON:

```json
{ "action": "tool_call", "tool": "get_pods", "arguments": { "namespace": "backend" } }
```

or

```json
{ "action": "final_answer", "answer": {...structured response...} }
```

We parse, execute, feed results back as user-role context.

## Auto mode (default)

```text
start native
     │
     ├─ provider rejects tools param (400)      → downgrade to prompted (rest of process)
     ├─ turn 1: no tool_calls AND content is
     │  neither structured output nor a tool
     │  request                                 → restart this request in prompted mode
     └─ otherwise                               → stay native
```

Once downgraded, the process stays downgraded — no repeated failed attempts.

## Iteration budget

Maximum 8 tool rounds per chat request. On exhaustion the loop forces a final answer with what it has ("tool budget reached"). Sequential execution only — no parallel calls.

---

# 6. Response transparency

`ChatResponse` gains:

```python
class ToolUsage(BaseModel):
    tool: str
    arguments: dict

class ChatResponse(BaseModel):
    answer: str
    reasoning_summary: str
    suggested_next_steps: list[str]
    tools_used: list[ToolUsage] = []
```

Phase 4 clients ignore the new field; nothing breaks.

---

# 7. Configuration additions

```python
default_namespace: str = "default"
agent_max_tool_iterations: int = 8
llm_tool_mode: str = "auto"        # auto | native | prompted
```

Default OpenRouter model changes to `meta-llama/llama-3.3-70b-instruct:free`
(supports native tools). `deepseek/deepseek-r1:free` still works via prompted
fallback but is no longer the recommended default.

---

# 8. System prompt rework

- Remove the "you cannot inspect clusters yet" clause.
- Add tool usage guidance and the diagnostic workflow hint:

```text
deployment → pods → events → logs → diagnosis
```

- Final answer must still be strict JSON matching the ChatResponse schema.
- If evidence is insufficient, say so honestly rather than inventing cluster state.

---

# 9. Error handling

| Failure | Behavior |
| --- | --- |
| Tool returns ApiException (404/403/etc.) | Serialized error result → LLM adapts |
| Model emits malformed tool arguments | Validation error result → LLM retries |
| Unknown tool name | Error result naming valid tools |
| Provider rejects tools parameter | Auto-downgrade to prompted mode |
| Iteration budget exhausted | Forced final answer with gathered evidence |
| Final output unparseable after retry | LLMParseError → HTTP 502 (unchanged from Phase 4) |

---

# 10. Testing strategy

A scripted mock drives the loop deterministically:

```python
ScriptedLLMClient([response_with_tool_calls, final_structured_answer])
```

Coverage:

- Single tool call round-trip (args validated, result fed back, final parsed)
- Multi-tool sequences (deployment → pods → events → logs)
- Invalid arguments / unknown tool / missing namespace → default applied
- Tool error captured as result, loop continues
- Max iterations enforced → forced final answer
- Fallback trigger: no native tool_calls + unparseable content → prompted retry
- Prompted-mode parsing (tool_call action, final_answer action, garbage)
- `tools_used` populated correctly
- Endpoint integration with mocked pieces; all Phase 4 tests stay green

---

# 11. What we explicitly DON'T do

### No mutations

Read-only tools only. RBAC enforces server-side regardless. Mutations are Phase 7+.

### No LangGraph / AgentState

The hand-rolled loop is small enough to understand completely. Frameworks arrive when there's a real workflow (Phase 6).

### No conversation history

Still single-turn. Each request starts fresh.

### No parallel tool execution

Sequential only — deterministic, easy to reason about, easy to test.

### No streaming

Unchanged from Phase 4.

---

# 12. Cost warning

Each chat request may consume up to ~9 LLM round-trips (8 tool rounds + final).
On OpenRouter free tier (20 req/min, 50 req/day) real diagnostic conversations
hit limits quickly. Development against `LLM_PROVIDER=mock` remains free and
unlimited.

---

# 13. Phase 5 milestones

| Milestone | Goal |
| --------- | ---- |
| **M5.1** | Extend `base.py`: `ToolCall`, richer `LLMMessage`, `complete(tools=)` |
| **M5.2** | Adapter updates: OpenAI-compatible tool payload/parsing + scripted mock |
| **M5.3** | Tool definitions, registry, safe executor |
| **M5.4** | Native agent loop with iteration budget |
| **M5.5** | Prompted fallback + auto-downgrade |
| **M5.6** | Wire into `chat_service`; `tools_used`; config additions |
| **M5.7** | System prompt rework |
| **M5.8** | Full test suite |
| **M5.9** | Live verification against OpenRouter (requires API key) |

Final architecture:

```text
                        HTTP
                         │
                         ▼
                  ┌─────────────┐
                  │   FastAPI   │
                  └──────┬──────┘
                         │
                         ▼
                  ┌─────────────┐
                  │ Agent Loop  │
                  └──────┬──────┘
                 native /│
            prompted ▼   ▼
              ┌────────────────┐
              │ BaseLLMClient  │
              └───────┬────────┘
                      ▼
                 openai SDK ──► OpenRouter / Groq / …
                      
              ┌────────────────────┐
              │  Tool Registry     │
              │  validate/default/ │
              │  truncate/capture  │
              └────────┬───────────┘
                       ▼
               KubernetesClient
                       ▼
                 Kubernetes API
```

---

## Our next step

Start with **M5.1–M5.2**: extend the interface types and adapters so any client
can express tool calls. Everything else builds on that foundation.
