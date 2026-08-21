# Phase 2 — Coding Flow

## Summary

Phase 2 connected the FastAPI application to a real Kubernetes cluster (Minikube) through a clean `KubernetesClient` abstraction. The API layer never touches the Kubernetes SDK directly — it depends on our own interface.

---

## What Was Built

### 1. Dependency Installation

Added the official Kubernetes Python client to `pyproject.toml`:

```
kubernetes>=31.0.0
```

Installed with `uv sync`. This brings in the SDK, aiohttp, and authentication libraries.

### 2. Project Structure

```
app/
├── kubernetes/
│   ├── __init__.py
│   ├── config.py          # kubeconfig loading
│   └── client.py          # KubernetesClient class
├── schemas/
│   └── kubernetes.py      # PodInfo, DeploymentInfo, ServiceInfo, EventInfo
├── api/v1/
│   └── kubernetes.py      # HTTP endpoints + error handling
└── main.py                # Updated: lifespan + router registration
```

### 3. kubeconfig Setup

- Minikube runs inside WSL
- Certificates were extracted from WSL using `base64 -w0`
- A self-contained `.kube/config` was created with embedded certificate data (no file references)
- Added `.kube/` to `.gitignore` to prevent credential leaks

### 4. app/kubernetes/config.py

Handles Kubernetes authentication:

```python
from kubernetes import config as k8s_config
from app.config import settings

def load_kubernetes_config() -> None:
    kubeconfig_path = settings.kubeconfig_file
    if kubeconfig_path.exists():
        k8s_config.load_kube_config(config_file=str(kubeconfig_path))
    else:
        k8s_config.load_kube_config()
```

- Checks project-level `.kube/config` first
- Falls back to system kubeconfig (`~/.kube/config`)
- Called once at application startup via FastAPI lifespan

### 5. app/kubernetes/client.py — KubernetesClient

Single class wrapping `CoreV1Api` and `AppsV1Api`:

```python
class KubernetesClient:
    def __init__(self):
        self._core = client.CoreV1Api()
        self._apps = client.AppsV1Api()

    async def get_pods(namespace) -> PodListResponse
    async def get_deployment(namespace, name) -> DeploymentInfo
    async def get_service(namespace, name) -> ServiceInfo
    async def get_pod_logs(namespace, pod_name) -> str
    async def get_events(namespace) -> list[EventInfo]
```

Key design decisions:

- Returns Pydantic models, not raw Kubernetes SDK objects
- Decodes pod logs from bytes to string
- Computes `ready` status from pod conditions
- Sums restart counts across containers
- Formats deployment conditions as `type=status` strings

### 6. app/schemas/kubernetes.py

Clean Pydantic models that control what leaves the Kubernetes layer:

```python
class PodInfo(BaseModel):
    name, namespace, status, ready, restart_count, node, created_at

class PodListResponse(BaseModel):
    items: list[PodInfo]

class DeploymentInfo(BaseModel):
    name, namespace, replicas, ready_replicas, updated_replicas,
    available_replicas, conditions

class ServiceInfo(BaseModel):
    name, namespace, type, cluster_ip, ports

class EventInfo(BaseModel):
    name, namespace, type, reason, message, count,
    first_seen, last_seen, involved_object
```

### 7. app/api/v1/kubernetes.py — HTTP Endpoints

Five endpoints following the `/clusters/{cluster}/namespaces/{namespace}/...` pattern:

```
GET /api/v1/clusters/{cluster}/namespaces/{namespace}/pods
GET /api/v1/clusters/{cluster}/namespaces/{namespace}/deployments/{name}
GET /api/v1/clusters/{cluster}/namespaces/{namespace}/services/{name}
GET /api/v1/clusters/{cluster}/namespaces/{namespace}/pods/{pod_name}/logs
GET /api/v1/clusters/{cluster}/namespaces/{namespace}/events
```

Error handling maps Kubernetes API exceptions:

- `ApiException(404)` → 404 with descriptive message
- `ApiException(403)` → 403 access denied
- `ApiException(401)` → 401 authentication failed
- `ApiException(5xx)` → 503 service unavailable
- Other exceptions → 500 internal error

### 8. app/main.py Updates

- Added `lifespan` async context manager to load Kubernetes config at startup
- Registered the Kubernetes router with `/api/v1` prefix

### 9. app/config.py Updates

Added `kubeconfig_file` setting:

```python
kubeconfig_file: Path = Path(".kube/config")
```

---

## Testing

### Unit Tests (11 total, all passing)

- `tests/test_kubernetes.py` — 7 tests with mocked KubernetesClient
  - `test_get_pods` — verifies endpoint calls client correctly
  - `test_get_deployment` — verifies endpoint calls client correctly
  - `test_get_service` — verifies endpoint calls client correctly
  - `test_get_pod_logs` — verifies endpoint calls client correctly
  - `test_get_events` — verifies endpoint calls client correctly
  - `test_k8s_error_404` — verifies 404 mapping
  - `test_k8s_error_403` — verifies 403 mapping

### Integration Tests Against Minikube

All five endpoints were verified against a live Minikube cluster:

- `GET .../kube-system/pods` — returned 7 pods with status/ready/restart info
- `GET .../kube-system/services/kube-dns` — returned ClusterIP with ports
- `GET .../kube-system/pods/{name}/logs` — returned decoded log output
- `GET .../kube-system/events` — returned 31 events
- `GET .../default/deployments/nonexistent` — returned 404

---

## Architecture

```
HTTP Request
     │
     ▼
  FastAPI
     │
  Dependency Injection
     │
     ▼
KubernetesClient
     │
  ┌──┴──┐
  ▼     ▼
CoreV1Api  AppsV1Api
  │     │
  └──┬──┘
     ▼
Kubernetes API Server
     │
     ▼
  Minikube
```

---

## Files Modified

| File             | Change                                |
| ---------------- | ------------------------------------- |
| `pyproject.toml` | Added `kubernetes>=31.0.0` dependency |
| `app/config.py`  | Added `kubeconfig_file` setting       |
| `app/main.py`    | Added lifespan, Kubernetes router     |
| `.gitignore`     | Added `.kube/` directory              |

## Files Created

| File                         | Purpose                       |
| ---------------------------- | ----------------------------- |
| `app/kubernetes/__init__.py` | Package init                  |
| `app/kubernetes/config.py`   | Kubernetes authentication     |
| `app/kubernetes/client.py`   | KubernetesClient class        |
| `app/schemas/kubernetes.py`  | Pydantic response models      |
| `app/api/v1/kubernetes.py`   | HTTP endpoints                |
| `.kube/config`               | Embedded Minikube credentials |
| `tests/test_kubernetes.py`   | Unit tests                    |
