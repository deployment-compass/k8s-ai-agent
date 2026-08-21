# k8s-ai-agent

AI-powered Kubernetes Operations Agent. Interact with your Kubernetes cluster using natural language.

## Status

| Phase | Milestone | Status |
|-------|-----------|--------|
| Phase 1 | FastAPI Foundation | Done |
| Phase 2 | Kubernetes Integration | Done |
| Phase 3 | Kubernetes RBAC | Done |
| Phase 4 | Introduce the LLM | Done |
| Phase 5 | Tool Calling | Done |
| Phase 5.1 | Agent Activity Logging | Done |
| Phase 5.2 | Expanded Diagnostics (21 tools) | Done |

## Tech Stack

| Component | Technology |
|-----------|------------|
| Language | Python 3.12 |
| Framework | FastAPI |
| Package Manager | uv |
| Validation | Pydantic |
| Kubernetes Client | Official `kubernetes` Python SDK |
| LLM | `openai` SDK (OpenRouter / Groq / Gemini / Ollama compatible) |
| Testing | pytest + httpx |

## Project Structure

```
k8s-ai-agent/
├── app/
│   ├── main.py                     # FastAPI app, lifespan, routing
│   ├── config.py                   # Pydantic Settings
│   ├── api/v1/
│   │   ├── chat.py                 # POST /api/v1/chat
│   │   └── kubernetes.py           # Kubernetes REST endpoints
│   ├── schemas/
│   │   ├── chat.py                 # ChatRequest/ChatResponse/ToolUsage
│   │   └── kubernetes.py           # PodInfo, DeploymentInfo, etc.
│   ├── services/
│   │   └── chat_service.py         # Chat orchestration (agent loop wiring)
│   ├── agent/
│   │   ├── loop.py                 # Agent loop: native tools + prompted fallback
│   │   ├── tools.py                # Tool registry, validation, safe executor
│   │   └── prompts.py              # System prompts (native + prompted modes)
│   ├── llm/
│   │   ├── base.py                 # BaseLLMClient interface + exceptions
│   │   ├── openai_compatible.py    # OpenAI-compatible adapter
│   │   ├── mock.py                 # Deterministic offline clients (mock + scripted)
│   │   ├── factory.py              # Provider selection from settings
│   │   └── parsing.py              # JSON extraction + validation
│   └── kubernetes/
│       ├── config.py               # Kubeconfig loading (local + in-cluster)
│       └── client.py               # KubernetesClient abstraction
├── k8s/
│   └── rbac.yaml                   # ServiceAccount, ClusterRole, ClusterRoleBinding
├── tests/
│   ├── test_health.py
│   ├── test_chat.py
│   ├── test_chat_service.py
│   ├── test_agent_loop.py
│   ├── test_agent_tools.py
│   ├── test_kubernetes.py
│   ├── test_llm_factory.py
│   └── test_llm_parsing.py
├── plan/                           # Development plans
├── pyproject.toml
├── uv.lock
└── .python-version
```

## Getting Started

### Prerequisites

- Python 3.12+
- [uv](https://docs.astral.sh/uv/)
- A running Kubernetes cluster (Minikube, Docker Desktop, etc.)
- `~/.kube/config` or project-level `.kube/config`

### Install

```bash
git clone <repo-url>
cd k8s-ai-agent
uv sync
```

### Run

```bash
uv run uvicorn app.main:app --reload
```

API docs at http://localhost:8000/docs

### Test

```bash
uv run pytest -v
```

## API Endpoints

### Health

```
GET /health
```

### Chat

```
POST /api/v1/chat
```

```json
{ "message": "What does CrashLoopBackOff mean?" }
```

Response:

```json
{
  "answer": "The backend deployment has 2 pods in CrashLoopBackOff ...",
  "reasoning_summary": "Inspected the deployment, pods, events, then logs.",
  "suggested_next_steps": ["Check database connectivity from the cluster"],
  "tools_used": [
    { "tool": "get_deployment", "arguments": { "namespace": "backend", "name": "backend" } },
    { "tool": "get_pods", "arguments": { "namespace": "backend" } },
    { "tool": "get_events", "arguments": { "namespace": "backend" } },
    { "tool": "get_pod_logs", "arguments": { "namespace": "backend", "pod_name": "backend-abc" } }
  ]
}
```

### Tool calling

With a real provider configured, the agent decides which read-only Kubernetes tools to call:

**Core (Phase 5):**

| Tool | Arguments |
|------|-----------|
| `get_pods` | namespace |
| `get_deployments` | namespace |
| `get_deployment` | namespace, name |
| `get_services` | namespace |
| `get_service` | namespace, name |
| `get_pod_logs` | namespace, pod_name |
| `get_events` | namespace |

**Diagnostics (Phase 5.2):**

| Tool | Arguments | Answers questions about |
|------|-----------|-------------------------|
| `describe_pod` | namespace, pod_name | Crash reasons: waiting states (`CrashLoopBackOff`, `ImagePullBackOff`), last termination (`OOMKilled`), exit codes, probes, resources, volumes, owner chain |
| `describe_deployment` | namespace, name | Rollout strategy, conditions with reasons, images, owned ReplicaSets |
| `get_namespaces` | — | Which namespaces exist |
| `get_endpoints` | namespace, service_name | Service backend pods; empty = selector mismatch or no ready pods |
| `get_pvcs` | namespace | Volume binding; Pending claims block pod startup |
| `get_nodes` | — | Node availability and kubelet versions |
| `describe_node` | node_name | Pressure conditions, taints, allocatable vs capacity |
| `get_replicasets` | namespace | Rollout history and revisions |
| `get_ingresses` | namespace | Host/routing rules, TLS hosts |
| `get_statefulsets` | namespace | Stateful workload health |
| `get_daemonsets` | namespace | Per-node agent rollout counts |
| `get_jobs` | namespace | Batch job status (active/succeeded/failed) |
| `get_cronjobs` | namespace | Schedules and last run time |
| `get_hpas` | namespace | Autoscaler targets and utilization |

Every `get_pods` result also embeds a `containers[]` list with live per-container
state and waiting/termination reasons.

The agent has **no access to ConfigMaps or Secrets** (not even names) — this is a
hard-coded limitation the system prompt makes it state explicitly when relevant.
Mutation tools arrive in Phase 7 behind the policy engine.

Behavior:
- **Native mode** (default): tools sent via the provider's function-calling API
- **Prompted fallback**: if the model/provider doesn't support native tools, tool descriptions are embedded in the prompt and the model answers with `{action: tool_call | final_answer}` JSON
- Omitted namespace falls back to `DEFAULT_NAMESPACE`
- Tool errors (404/403/...) are fed back to the model as reasoning material instead of failing the request
- Max `AGENT_MAX_TOOL_ITERATIONS` tool rounds per request, then a forced final answer
- Logs are truncated to the tail; large lists are capped

The LLM backend is selected via `LLM_PROVIDER`. With `LLM_PROVIDER=mock` (default) the endpoint returns deterministic offline responses. Configure a real provider by setting `LLM_API_KEY` (see Configuration).

**Chat error responses:**

| Code | Meaning |
|------|---------|
| 422 | Empty or missing message |
| 429 | LLM rate limit exceeded (`Retry-After` header when provided) |
| 500 | LLM authentication failed (check server config) |
| 502 | LLM provider unavailable or returned invalid output |
| 504 | LLM provider timed out |

### Kubernetes

All Kubernetes endpoints use the pattern:

```
GET /api/v1/clusters/{cluster}/namespaces/{namespace}/...
```

| Endpoint | Description |
|----------|-------------|
| `GET .../pods` | List all pods (with per-container states) |
| `GET .../deployments` | List all deployments |
| `GET .../deployments/{name}` | Get a specific deployment |
| `GET .../services` | List all services |
| `GET .../services/{name}` | Get a specific service |
| `GET .../pods/{pod_name}/logs` | Get pod logs |
| `GET .../events` | List all events |
| `GET .../pods/{pod_name}/describe` | Deep pod inspection (states, probes, volumes, owner chain) |
| `GET .../deployments/{name}/describe` | Deep deployment inspection (strategy, conditions, ReplicaSets) |
| `GET .../services/{name}/endpoints` | Service backend addresses and ports |
| `GET .../pvcs` | List persistent volume claims |
| `GET .../replicasets` | List ReplicaSets (rollout history) |
| `GET .../ingresses` | List ingresses |
| `GET .../statefulsets` | List statefulsets |
| `GET .../daemonsets` | List daemonsets |
| `GET .../jobs` | List jobs |
| `GET .../cronjobs` | List cronjobs |
| `GET .../hpas` | List horizontal pod autoscalers |

Cluster-scoped:

| Endpoint | Description |
|----------|-------------|
| `GET /api/v1/clusters/{cluster}/namespaces` | List namespaces |
| `GET /api/v1/clusters/{cluster}/nodes` | List nodes |
| `GET /api/v1/clusters/{cluster}/nodes/{name}/describe` | Deep node inspection (conditions, taints, capacity) |

**Examples:**

```bash
# List pods in kube-system
curl http://localhost:8000/api/v1/clusters/default/namespaces/kube-system/pods

# Get a specific deployment
curl http://localhost:8000/api/v1/clusters/default/namespaces/argocd/deployments/argocd-server

# Get pod logs
curl http://localhost:8000/api/v1/clusters/default/namespaces/kube-system/pods/coredns-xxx/logs
```

**Response models:**

| Model | Fields |
|-------|--------|
| `PodInfo` | name, namespace, status, ready, restart_count, node, created_at, containers[] (name, image, state, ready, restart_count, waiting_reason, last_termination_reason, exit_code) |
| `PodDescribe` | name, namespace, phase, node, created_at, conditions, init_containers[], containers[] (+probes, resources), volumes[], owner_chain, node_selector |
| `DeploymentInfo` | name, namespace, replicas, ready_replicas, updated_replicas, available_replicas, conditions |
| `DeploymentDescribe` | + strategy, max_surge/max_unavailable, selector, conditions (with reason/message), images, owned_replicasets[] |
| `ServiceInfo` | name, namespace, type, cluster_ip, ports |
| `EndpointsInfo` | name, namespace, addresses, not_ready_addresses, ports |
| `EventInfo` | name, namespace, type, reason, message, count, first_seen, last_seen, involved_object |
| `NamespaceInfo` | name, phase, created_at |
| `NodeInfo` / `NodeDescribe` | name, ready, kubelet_version / + unschedulable, conditions, taints, allocatable vs capacity, addresses |
| `PVCInfo` | name, namespace, phase, capacity, storage_class |
| `ReplicaSetInfo` | name, namespace, desired, ready, revision, owner_deployment |
| `IngressInfo` | name, namespace, rules (host, path→service), tls_hosts |
| `StatefulSetInfo` | name, namespace, replicas, ready_replicas, updated_replicas, conditions |
| `DaemonSetInfo` | name, namespace, desired_scheduled, ready, available, updated |
| `JobInfo` | name, namespace, active, succeeded, failed, completions, start_time |
| `CronJobInfo` | name, namespace, schedule, suspend, active_jobs, last_schedule_time |
| `HPAInfo` | name, namespace, target, min/max/current/desired replicas, target/current CPU utilization |

**Error responses:**

| Code | Meaning |
|------|---------|
| 404 | Resource not found |
| 403 | Access denied |
| 401 | Kubernetes authentication failed |
| 503 | Kubernetes API unavailable |

## Configuration

Environment variables (via `.env` or environment):

| Variable | Default | Description |
|----------|---------|-------------|
| `APP_ENV` | `development` | Application environment |
| `APP_DEBUG` | `true` | Enable debug mode |
| `APP_HOST` | `0.0.0.0` | Server host |
| `APP_PORT` | `8000` | Server port |
| `KUBECONFIG_FILE` | `.kube/config` | Path to kubeconfig |
| `LLM_PROVIDER` | `mock` | `mock`, `openrouter`, `groq`, `gemini`, `ollama`, `openai` |
| `LLM_API_KEY` | *(empty)* | Provider API key (not needed for mock/ollama) |
| `LLM_MODEL` | provider preset | Model ID, e.g. `meta-llama/llama-3.3-70b-instruct:free` |
| `LLM_BASE_URL` | provider preset | Override the OpenAI-compatible base URL |
| `LLM_TIMEOUT_SECONDS` | `30` | LLM request timeout |
| `LLM_TEMPERATURE` | `0.2` | Sampling temperature |
| `LLM_MAX_RETRIES` | `2` | HTTP-level retries inside the SDK |
| `LLM_TOOL_MODE` | `auto` | `auto` (native, falls back to prompted), `native`, `prompted` |
| `DEFAULT_NAMESPACE` | `default` | Namespace used when tool args omit it |
| `AGENT_MAX_TOOL_ITERATIONS` | `8` | Max tool-execution rounds per chat request |
| `AGENT_LOG_ENABLED` | `true` | Console logging of agent activity |
| `AGENT_LOG_LEVEL` | `INFO` | Log detail: `DEBUG` adds LLM timing, token usage, result previews |

### Agent activity logging

With `AGENT_LOG_ENABLED=true` the console shows what the agent is doing:

```text
2026-08-21 12:00:01,123 INFO app.services.chat_service Chat request received: 'Why is my backend unhealthy?'
2026-08-21 12:00:01,124 INFO app.agent.loop Agent loop starting: mode=native max_tool_iterations=8
2026-08-21 12:00:02,456 INFO app.agent.tools Tool call: get_pods args={'namespace': 'backend'}
2026-08-21 12:00:02,678 INFO app.agent.tools Tool result: get_pods status=ok size=412 duration=0.221s
2026-08-21 12:00:03,900 INFO app.agent.loop Agent loop complete: mode=native rounds=1 tool_calls=1 duration=2.78s (final answer produced)
```

Set `AGENT_LOG_LEVEL=DEBUG` to also see LLM request/response timing, token usage, and truncated tool-result previews. With `AGENT_LOG_ENABLED=false`, activity logs are silenced but errors still appear.

To use a free OpenRouter model:

```bash
cp .env.example .env
# set LLM_API_KEY=<your key from openrouter.ai>
```

## RBAC

The application uses least-privilege access via a dedicated ServiceAccount.

**Apply RBAC manifests (required before deploying):**

```bash
kubectl apply -f k8s/rbac.yaml
```

This creates 4 resources:
- Namespace `k8s-ai-agent`
- ServiceAccount `k8s-ai-agent`
- ClusterRole with read-only permissions
- ClusterRoleBinding linking the Role to the ServiceAccount

Kubernetes does not create custom ServiceAccounts for you. The `default` ServiceAccount in each namespace has no special permissions — your app would get 403 on everything without this step.

When deploying the app, specify the ServiceAccount in the pod spec:

```yaml
spec:
  serviceAccountName: k8s-ai-agent
```

Without that line, the pod uses `default` and has no access.

**What the app can do (all namespaces):**

| Resource | API group | Verbs |
|----------|-----------|-------|
| pods | core | get, list |
| pods/log | core | get |
| services | core | get, list |
| events | core | get, list |
| namespaces | core | get, list |
| endpoints | core | get, list |
| persistentvolumeclaims | core | get, list |
| nodes | core | get, list |
| deployments | apps | get, list |
| replicasets | apps | get, list |
| statefulsets | apps | get, list |
| daemonsets | apps | get, list |
| jobs | batch | get, list |
| cronjobs | batch | get, list |
| ingresses | networking.k8s.io | get, list |
| horizontalpodautoscalers | autoscaling | get, list |

**What the app cannot do:**

- Create, update, or delete any resource
- Access secrets or configmaps — no verbs granted, not even names
- Modify RBAC policies

**Auth behavior:**

| Environment | Authentication |
|-------------|----------------|
| Local development | `~/.kube/config` or `.kube/config` |
| In-cluster (Kubernetes) | ServiceAccount token |

The app automatically detects which environment it's running in.

## Architecture

```
HTTP Request
     │
     ▼
  FastAPI
     │
  KubernetesClient
     │
  ┌──┴────────────┬─────────────┬──────────────┐
  ▼               ▼             ▼              ▼
CoreV1Api    AppsV1Api    BatchV1Api   NetworkingV1Api / AutoscalingV2Api
  │               │             │              │
  └───────────────┴─────────────┴──────────────┘
                  │
                  ▼
            Kubernetes API
```

The `KubernetesClient` is the boundary between your application and the Kubernetes SDK. The API layer never imports or calls the SDK directly.

## Roadmap

- Phase 6: Agent state and reasoning workflow
- Phase 7: Mutation tools (restart, scale, patch)
- Phase 8: Human approval
- Phase 9: Post-action verification
- Phase 10: Audit logging
- Phase 11: Security hardening
- Phase 12: Containerize
- Phase 13: Deploy into Kubernetes
- Phase 14: Observability
- Phase 15: Advanced capabilities (multi-cluster, automatic remediation)
