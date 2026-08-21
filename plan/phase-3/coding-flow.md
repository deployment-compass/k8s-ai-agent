# Phase 3 — Coding Flow

## Summary

Phase 3 replaced the developer's full-access kubeconfig with a least-privilege ServiceAccount. The app now has a dedicated identity inside Kubernetes with read-only access to pods, deployments, services, events, and pod logs across all namespaces.

---

## What Was Built

### 1. RBAC Manifests — `k8s/rbac.yaml`

Created 4 Kubernetes resources in a single file:

```yaml
# Namespace
apiVersion: v1
kind: Namespace
metadata:
  name: k8s-ai-agent

---
# ServiceAccount
apiVersion: v1
kind: ServiceAccount
metadata:
  name: k8s-ai-agent
  namespace: k8s-ai-agent

---
# ClusterRole (cluster-wide, not namespaced)
apiVersion: rbac.authorization.k8s.io/v1
kind: ClusterRole
metadata:
  name: k8s-ai-agent
rules:
  - apiGroups: [""]
    resources: ["pods", "services", "events"]
    verbs: ["get", "list"]
  - apiGroups: [""]
    resources: ["pods/log"]
    verbs: ["get"]
  - apiGroups: ["apps"]
    resources: ["deployments"]
    verbs: ["get", "list"]

---
# ClusterRoleBinding
apiVersion: rbac.authorization.k8s.io/v1
kind: ClusterRoleBinding
metadata:
  name: k8s-ai-agent
subjects:
  - kind: ServiceAccount
    name: k8s-ai-agent
    namespace: k8s-ai-agent
roleRef:
  kind: ClusterRole
  name: k8s-ai-agent
  apiGroup: rbac.authorization.k8s.io
```

**Why ClusterRole instead of Role:**

The plan says "access all namespaces." Roles are namespace-scoped. ClusterRoles are cluster-scoped. Using ClusterRole + ClusterRoleBinding gives the app read access to pods/services/events/deployments in every namespace.

**Why these specific permissions:**

These are the exact resources the app's 7 API endpoints need. Nothing more. If the app tries anything else, Kubernetes rejects it with 403.

### 2. Authentication Update — `app/kubernetes/config.py`

Changed from kubeconfig-only to dual-mode authentication:

```python
def load_kubernetes_config() -> None:
    try:
        k8s_config.load_incluster_config()
    except k8s_config.ConfigException:
        kubeconfig_path = settings.kubeconfig_file
        if kubeconfig_path.exists():
            k8s_config.load_kube_config(config_file=str(kubeconfig_path))
        else:
            k8s_config.load_kube_config()
```

**Logic:**

1. Try `load_incluster_config()` — works when running inside a Kubernetes pod (reads token from `/var/run/secrets/kubernetes.io/serviceaccount/token`)
2. If that fails (we're local), fall back to `load_kube_config()` — uses `.kube/config`

This means:
- **Local development:** full access via your kubeconfig
- **In-cluster:** restricted access via ServiceAccount

### 3. README Update

Added RBAC section covering:
- How to apply the manifests
- What gets created (4 resources)
- That `default` ServiceAccount has no permissions
- That you need `serviceAccountName` in the pod spec
- Permissions table (what can/cannot do)
- Auth behavior table (local vs in-cluster)

---

## Verification

### RBAC Permissions Test

Applied manifests to Minikube and tested with `kubectl auth can-i`:

```
✅ get pods               — yes
✅ list pods              — yes
✅ get pods/log           — yes
✅ get deployments        — yes
✅ list deployments       — yes
✅ get services           — yes
✅ list services          — yes
✅ get events             — yes
✅ list events            — yes

❌ delete pods            — no
❌ delete namespaces      — no
❌ get secrets            — no
```

### Unit Tests

All 13 existing tests still pass (no code changes to test — RBAC is infrastructure, not application code).

---

## Architecture

```
Local Development              In-Cluster
      │                            │
      ▼                            ▼
kubeconfig (.kube/config)    ServiceAccount token
      │                            │
      ▼                            ▼
   Full Access               Read-Only Access
      │                            │
      └──────────┬─────────────────┘
                 │
                 ▼
          KubernetesClient
```

---

## Key Decisions

| Decision | Choice | Reason |
|----------|--------|--------|
| Role vs ClusterRole | ClusterRole | App needs access to all namespaces |
| RoleBinding vs ClusterRoleBinding | ClusterRoleBinding | Matches ClusterRole scope |
| Namespace | Dedicated `k8s-ai-agent` | Isolation from other workloads |
| Auth fallback | kubeconfig | Allows local development without ServiceAccount |

---

## Files Modified

| File | Change |
|------|--------|
| `app/kubernetes/config.py` | Added in-cluster auth fallback |
| `README.md` | Added RBAC section, updated status |

## Files Created

| File | Purpose |
|------|---------|
| `k8s/rbac.yaml` | ServiceAccount, ClusterRole, ClusterRoleBinding, Namespace |

---

## How to Deploy

```bash
# Apply RBAC
kubectl apply -f k8s/rbac.yaml

# When deploying the app, specify the ServiceAccount:
# spec:
#   serviceAccountName: k8s-ai-agent
```

Without `serviceAccountName`, the pod uses `default` — which has no permissions.
