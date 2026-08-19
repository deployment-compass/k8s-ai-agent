# Phase 1 (Project Bootstrap)

## 1. Technical Decisions & Stack

Our overarching philosophy is **progressive enhancement**. We are only installing what we need to route an HTTP request to a dummy service layer and return a response.

| Category            | Selection          | Rationale                                                           |
| ------------------- | ------------------ | ------------------------------------------------------------------- |
| **Language**        | Python 3.12        | Balances modern features with broad AI/K8s ecosystem compatibility. |
| **Framework**       | FastAPI            | Async-first, automatic OpenAPI docs, typed requests.                |
| **Package Manager** | `uv`               | Fast, deterministic dependency resolution and lockfiles.            |
| **Project Config**  | `pyproject.toml`   | Standardized Python project configuration.                          |
| **Validation**      | Pydantic           | Strict data contracts at the API boundary.                          |
| **Configuration**   | Pydantic Settings  | Environment variables parsed into typed objects.                    |
| **Testing**         | `pytest` + `httpx` | Standard testing suite mimicking real HTTP requests.                |

## 2. Deferred Scope (What we are NOT doing)

To maintain velocity and isolate debugging, the following are explicitly out of scope for Phase 1:

- **No Kubernetes:** The `kubernetes` client will be added in Phase 2.
- **No LLMs/Agents:** LangGraph, OpenAI, or other model SDKs are deferred until Phase 4/5.
- **No Database:** No persistence layer until auditing/memory is required.
- **No Auth:** We will build the core loop locally first.

## 3. Target Architecture

The repository will be named **`k8s-ai-agent`** to reflect the domain, rather than the underlying framework. By the end of this phase, the project will match this structure:

```text
k8s-ai-agent/
├── pyproject.toml
├── uv.lock
├── .python-version
├── .env.example
├── .gitignore
│
├── app/
│   ├── main.py                 # App composition & routing only
│   ├── config.py               # Pydantic settings loading
│   │
│   ├── api/
│   │   └── v1/
│   │       └── chat.py         # HTTP concerns (POST /api/v1/chat)
│   │
│   ├── schemas/
│   │   └── chat.py             # Data contracts (ChatRequest/Response)
│   │
│   └── services/
│       └── chat_service.py     # Business logic (Dummy responses for now)
│
└── tests/
    ├── test_health.py          # Verifies app startup
    └── test_chat.py            # Verifies API contracts

```

---

## 4. Execution Sequence: The Bootstrap

As requested, we will execute this systematically, one step at a time, validating at each checkpoint.

**Step 1: Project Initialization**

- Create the repository and initialize it with `uv`.
- Pin the environment to Python 3.12.

**Step 2: Core Dependencies**

- Add the minimal production dependencies (`fastapi`, `uvicorn`, `pydantic-settings`).
- Add the development dependencies (`pytest`, `httpx`).

**Step 3: Scaffold the Architecture**

- Create the directory tree (`app/`, `api/`, `schemas/`, `services/`, `tests/`).

**Step 4: The Minimal Application**

- Write `schemas/chat.py` (the data contract).
- Write `services/chat_service.py` (the dummy logic).
- Write `api/v1/chat.py` (the router).
- Wire them together in `main.py` along with a `/health` endpoint.

**Step 5: Verification**

- Run the development server.
- Verify `/health` via `curl` or browser.
- Verify the `/api/v1/chat` endpoint.
- Write and run the initial `pytest` suite to lock in the behavior.
