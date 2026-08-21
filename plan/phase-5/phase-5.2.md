# Phase 5.2 — Expanded Kubernetes Diagnostics

## 1. Objective

After Phase 5, the agent can see *what* is failing but often not *why*.
Current `PodInfo` exposes name/status/ready/restart_count only — the actual
crash reason (`OOMKilled`, `ImagePullBackOff`, `CreateContainerConfigError`)
lives in container waiting-reasons that are never captured.

Phase 5.2 roughly doubles the read-only diagnostic surface: enriched pod data,
kubectl-style `describe_*` views, and coverage of every common failure domain
(storage, scheduling, networking, workloads, autoscaling) — as both agent tools
and REST endpoints.

---

# 2. Decisions made

| Decision | Choice | Reason |
| --- | --- | --- |
| Scope | All tiers | Full "why is it broken" coverage |
| ConfigMaps / Secrets | No tools, no RBAC, hard-coded limitation note | Even names leak attack surface; master plan forbids Secret access |
| Exposure | Agent tools + REST endpoints | Consistent with Phase 2 pattern |
| Naming | `describe_*` prefix | Mirrors kubectl vocabulary the LLM already knows |

---

# 3. New tools (14)

## Tier 1 — Critical gaps

| Tool | Arguments | Key fields returned |
| --- | --- | --- |
| `get_namespaces` | — | name, status, created_at |
| `describe_pod` | namespace, pod_name | per-container state (`running/waiting/terminated`), **waiting_reason, exit_code**, restarts, probes, resource requests/limits, volumes, owner chain (pod→RS→Deployment) |
| `describe_deployment` | namespace, name | strategy, selector, conditions detail, pod template summary, owned ReplicaSets |

Plus **`PodInfo` enrichment**: every existing `get_pods` result gains a
`containers[]` list with live state + waiting reasons. This fixes the biggest
blind spot even when the agent doesn't call describe.

## Tier 2 — Common failure domains

| Tool | Arguments | Key fields returned |
| --- | --- | --- |
| `get_endpoints` | namespace, service_name | addresses + ports; empty endpoints = selector mismatch flag |
| `get_pvcs` | namespace | name, phase (Bound/Pending), capacity, storage_class |
| `get_nodes` | — | name, Ready condition, kubelet version |
| `describe_node` | node_name | conditions (pressure/taints), allocatable vs capacity (CPU/mem/pods), addresses |
| `get_replicasets` | namespace | name, desired/ready replicas, owner deployment |

## Tier 3 — Situational

| Tool | Arguments | Key fields returned |
| --- | --- | --- |
| `get_ingresses` | namespace | hosts, rules (path→service), TLS |
| `get_statefulsets` | namespace | same shape as deployments |
| `get_daemonsets` | namespace | desired/ready/available counts |
| `get_jobs` | namespace | succeeded/failed/active, completions, start time |
| `get_cronjobs` | namespace | schedule, suspend, last_schedule_time |
| `get_hpas` | namespace | target ref, current/target replicas, CPU utilization |

Total tool count after this phase: **21**.

---

# 4. REST endpoints

Namespaced (existing `/api/v1/clusters/{cluster}/namespaces/{namespace}` prefix):

```text
GET .../pods/{pod_name}/describe
GET .../deployments/{name}/describe
GET .../services/{name}/endpoints
GET .../pvcs
GET .../replicasets
GET .../ingresses
GET .../statefulsets
GET .../daemonsets
GET .../jobs
GET .../cronjobs
GET .../hpas
```

Cluster-scoped:

```text
GET /api/v1/clusters/{cluster}/namespaces          # list namespaces
GET /api/v1/clusters/{cluster}/nodes
GET /api/v1/clusters/{cluster}/nodes/{name}/describe
```

Error mapping reuses the central `_handle_k8s_error` from Phase 2.

---

# 5. RBAC additions — `k8s/rbac.yaml`

Read-only verbs (`get`, `list`) added to the existing ClusterRole:

```text
core (""):
    namespaces, endpoints, persistentvolumeclaims, nodes

apps:
    replicasets, statefulsets, daemonsets   (+ existing deployments)

batch:
    jobs, cronjobs

networking.k8s.io:
    ingresses

autoscaling:
    horizontalpodautoscalers
```

Explicitly NOT granted: configmaps, secrets (any verb).

Nodes are cluster-scoped; the existing ClusterRole scope already covers them.

---

# 6. Security posture

### Hard-coded limitation note (system prompt)

Added to `app/agent/prompts.py` base prompt:

> You have NO access to ConfigMaps or Secrets (not even their names).
> If diagnosis requires them, state this limitation explicitly in your answer.

No tool exists for either resource, so any attempt returns the standard
unknown-tool error. The note sets expectations so the model explains the gap
instead of hallucinating values.

### Context window safety

- `describe_*` handlers return curated fields, never raw SDK dumps
- Existing truncation caps apply to all new tool results
- List endpoints capped by `MAX_LIST_ITEMS`

---

# 7. Testing strategy

- `tests/test_kubernetes.py`: mocked endpoint tests for every new route,
  including error mapping reuse (404/403 paths)
- `tests/test_agent_tools.py`: definitions cover all 21 tools;
  validation/defaulting still applies to new tools
- Schema serialization covered via endpoint response models
- All existing tests stay green (`PodInfo` gains an additive field)

---

# 8. Milestones

| Milestone | Goal |
| --------- | ---- |
| **M5.2.1** | Schemas: enrich `PodInfo`, add ~15 new Pydantic models |
| **M5.2.2** | 14 new `KubernetesClient` methods |
| **M5.2.3** | RBAC manifest update |
| **M5.2.4** | REST endpoints with reused error mapping |
| **M5.2.5** | Tool definitions + registry wiring (21 tools) |
| **M5.2.6** | System prompt limitation note |
| **M5.2.7** | Tests green across endpoint/tool layers |
| **M5.2.8** | README documentation update |

---

# 9. What we explicitly DON'T do

### No ConfigMaps or Secrets

Not names, not existence checks, not contents. Hard-coded out.

### No mutations

Still read-only. Mutation tools remain Phase 7 behind the policy engine.

### No metrics-server dependent tools

`kubectl top` equivalents (container/node resource usage) require the
metrics API and are deferred; capacity questions are answered via
allocatable/capacity in `describe_node`.

### No cross-namespace queries

Every namespaced tool takes exactly one namespace, consistent with the
existing surface and RBAC shape.
