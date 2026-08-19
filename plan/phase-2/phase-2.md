# Phase 2 — Kubernetes Integration

## 1. Phase objective

At the end of Phase 2, you should be able to do this:

```text
HTTP Request
     │
     ▼
  FastAPI
     │
     ▼
KubernetesClient
     │
     ▼
Kubernetes Python SDK
     │
     ▼
Kubernetes API Server
     │
     ▼
   Minikube
```

For example:

```http
GET /clusters/default/namespaces/backend/pods
```

and receive structured information about the pods.

The important part is that **the API endpoint should not directly contain Kubernetes SDK code**.

---

# 2. What we're going to build

I'd slightly refine the original structure.

```text
app/
├── main.py
├── api/
│   ├── chat.py
│   └── kubernetes.py
├── kubernetes/
│   ├── client.py
│   └── config.py
├── models/
│   └── schemas.py
└── config.py
```

The responsibilities should be:

| Component              | Responsibility                  |
| ---------------------- | ------------------------------- |
| `api/kubernetes.py`    | HTTP endpoints                  |
| `kubernetes/client.py` | Kubernetes operations           |
| `kubernetes/config.py` | Kubernetes client configuration |
| `models/schemas.py`    | API request/response models     |
| `config.py`            | Application configuration       |
| `main.py`              | FastAPI application             |

This separation is important because later the **agent will use the Kubernetes layer directly**, rather than going through your HTTP API.

---

# 3. First decision: Kubernetes Python client

We'll use the official Kubernetes Python client.

Conceptually:

```python
from kubernetes import client, config
```

There are two important ways your application can authenticate.

### During local development

```text
FastAPI
   │
   ▼
~/.kube/config
   │
   ▼
Minikube
```

You use:

```python
config.load_kube_config()
```

### Later, inside Kubernetes

```text
FastAPI Pod
   │
   ▼
ServiceAccount
   │
   ▼
Kubernetes API
```

You use:

```python
config.load_incluster_config()
```

**We will start with `load_kube_config()` because you're developing locally.**

Don't mix the two mechanisms yet.

---

# 4. First milestone: establish connectivity

Before implementing any endpoint, we want to answer:

> **Can my FastAPI application successfully authenticate with Kubernetes and communicate with the API server?**

The simplest test is retrieving namespaces or pods.

For example:

```text
FastAPI
   │
   │ Kubernetes Python SDK
   ▼
Kubernetes API Server
   │
   ▼
Minikube
```

If this doesn't work, we stop and fix it before continuing.

This gives us our first checkpoint:

### M2.1

**FastAPI → Kubernetes API connectivity works.**

---

# 5. Second milestone: create `KubernetesClient`

We don't want this:

```python
@app.get("/pods")
def get_pods():
    v1 = client.CoreV1Api()
    return v1.list_namespaced_pod(...)
```

inside the API layer.

Instead:

```text
API
 │
 ▼
KubernetesClient
 │
 ▼
CoreV1Api
```

For example, conceptually:

```python
class KubernetesClient:

    def get_pods(self, namespace):
        ...

    def get_pod_logs(self, namespace, pod_name):
        ...

    def get_service(self, namespace, name):
        ...

    def get_deployment(self, namespace, name):
        ...

    def get_events(self, namespace):
        ...
```

This class becomes your application's **Kubernetes boundary**.

Later the agent doesn't need to understand Kubernetes SDK details.

It simply has:

```text
get_pods
get_deployment
get_service
get_pod_logs
get_events
```

That's exactly what we'll eventually expose as LLM tools.

---

# 6. Kubernetes APIs we'll use

Kubernetes resources aren't all handled by the same API.

For example:

### Pods, Services, Logs, Events

These are primarily handled through:

```python
CoreV1Api
```

For example:

```text
CoreV1Api
 ├── list_namespaced_pod()
 ├── read_namespaced_pod_log()
 ├── read_namespaced_service()
 └── list_namespaced_event()
```

### Deployments

Deployments belong to the Apps API:

```python
AppsV1Api
```

For example:

```text
AppsV1Api
 └── read_namespaced_deployment()
```

This is worth understanding rather than hiding immediately behind abstractions.

---

# 7. The five operations for Phase 2

We'll implement exactly these first:

### 1. `get_pods`

```text
namespace
    ↓
Kubernetes API
    ↓
Pods
```

### 2. `get_deployment`

```text
namespace + deployment name
        ↓
Deployment
```

### 3. `get_service`

```text
namespace + service name
        ↓
Service
```

### 4. `get_pod_logs`

```text
namespace + pod name
        ↓
Pod logs
```

### 5. `get_events`

```text
namespace
    ↓
Events
```

These five are enough to build the first diagnostic agent later.

---

# 8. Important design decision: don't return raw Kubernetes objects

The Kubernetes Python SDK returns fairly large Python objects.

For example, a Pod contains a lot of information:

```text
metadata
spec
status
containers
volumes
owner references
conditions
...
```

You don't necessarily want to expose the entire SDK object directly through your API.

Instead:

```text
Kubernetes SDK object
        ↓
Your application model
        ↓
API response
```

For example:

```json
{
  "name": "backend-7d9c8",
  "namespace": "backend",
  "status": "Running",
  "ready": true
}
```

This is much cleaner.

It also becomes extremely important later when sending Kubernetes information to the LLM.

You don't want to dump enormous Kubernetes objects into the model context unnecessarily.

---

# 9. Define your own schemas

For example, conceptually:

```python
class PodInfo(BaseModel):
    name: str
    namespace: str
    status: str
    ready: bool
```

Then:

```python
class PodListResponse(BaseModel):
    items: list[PodInfo]
```

Your architecture becomes:

```text
Kubernetes
     │
     ▼
Kubernetes SDK object
     │
     ▼
KubernetesClient
     │
     ▼
Pydantic model
     │
     ▼
FastAPI
     │
     ▼
JSON
```

This gives you control over what information leaves the Kubernetes layer.

---

# 10. API design

I'd keep the Phase 2 API very simple.

Something along these lines:

```text
GET /clusters/default/namespaces/{namespace}/pods
```

```text
GET /clusters/default/namespaces/{namespace}/deployments/{name}
```

```text
GET /clusters/default/namespaces/{namespace}/services/{name}
```

```text
GET /clusters/default/namespaces/{namespace}/pods/{pod_name}/logs
```

```text
GET /clusters/default/namespaces/{namespace}/events
```

For example:

```http
GET /clusters/default/namespaces/backend/pods
```

Response:

```json
{
  "items": [
    {
      "name": "backend-7d9c8",
      "namespace": "backend",
      "status": "Running",
      "ready": true
    }
  ]
}
```

---

# 11. Why include `/clusters/default/`?

You might wonder:

> "I'm only using Minikube. Why do we need clusters?"

Because **multi-cluster support is eventually part of the project**.

Eventually:

```text
/clusters/dev/...
/clusters/staging/...
/clusters/production/...
```

could represent different clusters.

But we don't need to implement multi-cluster functionality yet.

For Phase 2:

```text
default → Minikube
```

That's enough.

We're simply keeping the API structure extensible.

---

# 12. Error handling

This is another important part of Phase 2.

Suppose the user asks for:

```text
backend
```

but the namespace doesn't exist.

Kubernetes returns an error.

Your application shouldn't return a giant Kubernetes SDK traceback.

Instead:

```http
404 Not Found
```

with something like:

```json
{
  "detail": "Namespace 'backend' not found."
}
```

Similarly:

```text
Pod doesn't exist
       ↓
404
```

```text
Kubernetes authentication failure
       ↓
500/appropriate server error
```

```text
Kubernetes API unavailable
       ↓
503 Service Unavailable
```

The exact mapping should be designed rather than handled randomly in each endpoint.

---

# 13. Configuration

We should also decide where Kubernetes configuration belongs.

I recommend keeping it separate from your normal application configuration.

Conceptually:

```text
app/config.py
        │
        └── application settings

app/kubernetes/config.py
        │
        └── Kubernetes configuration
```

For local development:

```text
KUBECONFIG
    ↓
load_kube_config()
```

Later:

```text
ServiceAccount
    ↓
load_incluster_config()
```

The rest of your application shouldn't care which authentication mechanism is being used.

---

# 14. Dependency injection

This is where your Phase 1 FastAPI knowledge becomes useful.

Instead of creating a Kubernetes client everywhere:

```python
client = KubernetesClient()
```

we can eventually use FastAPI dependency injection:

```text
Request
   │
   ▼
FastAPI dependency
   │
   ▼
KubernetesClient
   │
   ▼
Endpoint
```

This will make testing easier.

For example, during unit tests you can replace:

```text
Real KubernetesClient
```

with:

```text
FakeKubernetesClient
```

without needing a real cluster.

This is a design decision worth making early.

---

# 15. Testing strategy

Don't just test the HTTP endpoints.

We'll test at multiple levels.

### Level 1 — Kubernetes connectivity

```text
Python
 ↓
Kubernetes API
```

Can we actually connect?

### Level 2 — KubernetesClient

```text
KubernetesClient
 ↓
Kubernetes
```

Does:

```python
get_pods()
```

work?

### Level 3 — API

```text
HTTP
 ↓
FastAPI
 ↓
KubernetesClient
```

Does:

```text
GET /pods
```

produce the correct response?

### Level 4 — Error cases

Test:

```text
nonexistent namespace
nonexistent pod
nonexistent deployment
Kubernetes unavailable
invalid parameters
```

---

# 16. What we explicitly DON'T do

This is important.

### No LLM

Not yet.

```text
FastAPI → Kubernetes
```

not:

```text
FastAPI → LLM → Kubernetes
```

### No mutations

We only implement:

```text
GET
```

operations.

No:

```text
delete
patch
scale
restart
```

### No RBAC modifications

That's Phase 3.

Initially we're simply using your local kubeconfig against Minikube.

### No LangGraph

Not yet.

### No autonomous behavior

Definitely not yet.

---

# 17. Phase 2 milestones

I'd break the phase into these checkpoints:

| Milestone | Goal                                        |
| --------- | ------------------------------------------- |
| **M2.1**  | Install/configure Kubernetes Python client  |
| **M2.2**  | Establish FastAPI → Kubernetes connectivity |
| **M2.3**  | Implement `KubernetesClient` abstraction    |
| **M2.4**  | Implement pod operations                    |
| **M2.5**  | Implement deployment/service operations     |
| **M2.6**  | Implement logs/events                       |
| **M2.7**  | Create Pydantic response models             |
| **M2.8**  | Expose Kubernetes endpoints through FastAPI |
| **M2.9**  | Add error handling                          |
| **M2.10** | Add tests                                   |
| **M2.11** | Test everything against Minikube            |

The final Phase 2 architecture should look like:

```text
                       HTTP
                        │
                        ▼
                 ┌─────────────┐
                 │   FastAPI   │
                 │    API      │
                 └──────┬──────┘
                        │
                  Dependency
                   Injection
                        │
                        ▼
              ┌──────────────────┐
              │ KubernetesClient │
              └────────┬─────────┘
                       │
             ┌─────────┴─────────┐
             │                   │
             ▼                   ▼
       CoreV1Api             AppsV1Api
             │                   │
             └─────────┬─────────┘
                       ▼
              Kubernetes API
                       │
                       ▼
                    Minikube
```

---

# 18. The key architectural decision we'll make before coding

Before we write anything, I want us to settle **how the Kubernetes client should be structured**.

There are two reasonable approaches:

### Approach A — One `KubernetesClient`

```python
class KubernetesClient:
    def get_pods(...)
    def get_deployment(...)
    def get_service(...)
    def get_logs(...)
    def get_events(...)
```

Simple and appropriate for our MVP.

### Approach B — Separate resource clients

```text
KubernetesClient
 ├── PodClient
 ├── DeploymentClient
 ├── ServiceClient
 └── EventClient
```

More scalable, but introduces additional abstraction before we actually need it.

**For this project, I'd start with Approach A.** The five operations are small enough that one façade is clean, and we can refactor later if the domain grows.

The deeper principle is:

> **Keep Kubernetes SDK details inside one boundary so that the rest of the application depends on your own interface, not directly on the Kubernetes SDK.**

---

## Our next step

I suggest we **don't start writing Phase 2 code yet**.

Since you previously wanted to understand every decision before implementing, the next step should be **M2.1: understand exactly how the Kubernetes Python client works and how your local kubeconfig allows Python to authenticate with Minikube**.

We'll go through:

```text
Kubernetes API architecture
        ↓
Kubernetes Python client
        ↓
kubeconfig
        ↓
load_kube_config()
        ↓
CoreV1Api / AppsV1Api
        ↓
First connectivity test
```
