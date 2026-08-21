# k8s-ai-agent

AI-powered Kubernetes Operations Agent. Interact with your Kubernetes cluster using natural language.

## Status

| Phase | Milestone | Status |
|-------|-----------|--------|
| Phase 1 | FastAPI Foundation | Done |
| Phase 2 | Kubernetes Integration | Done |
| Phase 3 | Kubernetes RBAC | Done |
| Phase 4 | Introduce the LLM | Pending |

## Tech Stack

| Component | Technology |
|-----------|------------|
| Language | Python 3.12 |
| Framework | FastAPI |
| Package Manager | uv |
| Validation | Pydantic |
| Kubernetes Client | Official `kubernetes` Python SDK |
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
│   │   ├── chat.py                 # ChatRequest/ChatResponse
│   │   └── kubernetes.py           # PodInfo, DeploymentInfo, etc.
│   ├── services/
│   │   └── chat_service.py         # Chat business logic
│   └── kubernetes/
│       ├── config.py               # Kubeconfig loading (local + in-cluster)
│       └── client.py               # KubernetesClient abstraction
├── k8s/
│   └── rbac.yaml                   # ServiceAccount, ClusterRole, ClusterRoleBinding
├── tests/
│   ├── test_health.py
│   ├── test_chat.py
│   └── test_kubernetes.py
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
{ "message": "Why is my backend unhealthy?" }
```

### Kubernetes

All Kubernetes endpoints use the pattern:

```
GET /api/v1/clusters/{cluster}/namespaces/{namespace}/...
```

| Endpoint | Description |
|----------|-------------|
| `GET .../pods` | List all pods |
| `GET .../deployments` | List all deployments |
| `GET .../deployments/{name}` | Get a specific deployment |
| `GET .../services` | List all services |
| `GET .../services/{name}` | Get a specific service |
| `GET .../pods/{pod_name}/logs` | Get pod logs |
| `GET .../events` | List all events |

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
| `PodInfo` | name, namespace, status, ready, restart_count, node, created_at |
| `DeploymentInfo` | name, namespace, replicas, ready_replicas, updated_replicas, available_replicas, conditions |
| `ServiceInfo` | name, namespace, type, cluster_ip, ports |
| `EventInfo` | name, namespace, type, reason, message, count, first_seen, last_seen, involved_object |

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

| Resource | Verbs |
|----------|-------|
| pods | get, list |
| pods/log | get |
| deployments | get, list |
| services | get, list |
| events | get, list |

**What the app cannot do:**

- Create, update, or delete any resource
- Access secrets, configmaps, or namespaces
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
  ┌──┴──┐
  ▼     ▼
CoreV1Api  AppsV1Api
  │     │
  └──┬──┘
     ▼
Kubernetes API
```

The `KubernetesClient` is the boundary between your application and the Kubernetes SDK. The API layer never imports or calls the SDK directly.

## Roadmap

- Phase 4: LLM integration (system messages, context windows, structured output)
- Phase 5: Tool calling (LLM selects Kubernetes tools)
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
