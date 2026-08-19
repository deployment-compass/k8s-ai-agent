# AI Kubernetes Agent — Development Plan

## Project Goal

Build an AI-powered Kubernetes Operations Agent using FastAPI, an LLM, and the Kubernetes API.

The system should allow users to interact with Kubernetes using natural language while enforcing controlled tool access, Kubernetes RBAC, policy checks, human approval for risky operations, verification, and audit logging.

Core principle:

> LLM = reasoning engine  
> Tools = capabilities  
> Policy engine = safety boundary  
> Kubernetes API = execution layer  
> FastAPI = interface and orchestration layer

---

# Phase 0 — Define the MVP

**Goal:** Define exactly what Version 1 can and cannot do.

## V1 capabilities

The user should be able to ask:

> "Why is my backend deployment unhealthy?"

The agent should be able to:

- Inspect pods
- Inspect deployments
- Inspect services
- Read pod logs
- Inspect Kubernetes events
- Reason about the problem
- Explain its diagnosis

Initial modification capabilities may include:

- Restarting a pod
- Scaling a deployment
- Patching a deployment

All mutations should initially require human approval.

## Out of scope for V1

- Deleting namespaces
- Modifying RBAC
- Modifying Secrets
- Arbitrary `kubectl` execution
- Arbitrary shell commands
- Autonomous production changes

---

# Phase 1 — FastAPI Foundation

**Goal:** Create the backend application.

Suggested structure:

```text
app/
├── main.py
├── api/
│   └── chat.py
├── models/
│   └── schemas.py
└── config.py
```

Create initial endpoints:

```text
POST /chat
GET  /health
```

Example request:

```json
{
  "message": "Why is my backend unhealthy?"
}
```

Initially, `/chat` can return a dummy response.

## Learn

- FastAPI
- Pydantic
- Async/await
- Dependency injection
- Configuration management
- Exception handling

## Deliverable

A working FastAPI service running locally.

---

# Phase 2 — Kubernetes Integration

**Goal:** Make FastAPI communicate with Kubernetes before involving an LLM.

Suggested structure:

```text
app/
└── kubernetes/
    ├── client.py
    └── config.py
```

Create a Kubernetes abstraction:

```python
class KubernetesClient:
    def get_pods(...)
    def get_deployment(...)
    def get_service(...)
    def get_logs(...)
    def get_events(...)
```

## Initial Kubernetes capabilities

- `get_pods`
- `get_deployment`
- `get_service`
- `get_pod_logs`
- `get_events`

Test against a local cluster such as Minikube.

## Deliverable

FastAPI can retrieve structured information from the Kubernetes cluster.

---

# Phase 3 — Kubernetes RBAC

**Goal:** Give the application controlled, least-privilege Kubernetes access.

Architecture:

```text
ServiceAccount
      ↓
Role
      ↓
RoleBinding
```

Initially allow only:

```text
pods:
    get
    list

pods/log:
    get

deployments:
    get
    list

services:
    get
    list

events:
    get
    list
```

Do not allow mutations yet.

## Security test

Attempt an operation that the application should not be allowed to perform, such as deleting a namespace. It should fail.

## Deliverable

The application has controlled, read-only Kubernetes access.

---

# Phase 4 — Introduce the LLM

**Goal:** Connect the FastAPI application to an LLM.

Initial architecture:

```text
POST /chat
     │
     ▼
 FastAPI
     │
     ▼
   LLM
     │
     ▼
Response
```

Initially, do not provide Kubernetes tools.

Test questions such as:

- What does `CrashLoopBackOff` mean?
- What information should be inspected when diagnosing a failing deployment?

## Learn

- System and user messages
- Context windows
- Structured output
- JSON schemas
- Model configuration
- API error handling

## Deliverable

A working `/chat` endpoint powered by an LLM.

---

# Phase 5 — Tool Calling

**Goal:** Allow the LLM to use controlled Kubernetes tools.

Available tools:

```text
get_pods()
get_deployment()
get_logs()
get_events()
```

Workflow:

```text
User
 │
 ▼
LLM
 │
 │ "I need to inspect the pods"
 ▼
get_pods()
 │
 ▼
Kubernetes
 │
 ▼
Tool result
 │
 ▼
LLM
 │
 ▼
Final answer
```

Example request:

> "Why is the backend broken?"

Possible workflow:

```text
get_deployment()
       ↓
get_pods()
       ↓
get_events()
       ↓
get_logs()
       ↓
Diagnosis
```

## Deliverable

The first real Kubernetes AI agent: natural language → tool selection → real cluster inspection → diagnosis.

---

# Phase 6 — Agent State and Reasoning Workflow

**Goal:** Make the agent workflow predictable and controlled.

Example state:

```text
AgentState

{
    user_request,
    namespace,
    resources_inspected,
    findings,
    proposed_action,
    approval_status,
    execution_result
}
```

Workflow:

```text
START
  │
  ▼
Understand request
  │
  ▼
Inspect cluster
  │
  ▼
Diagnose
  │
  ▼
Need modification?
  │
 ┌┴──────┐
No       Yes
│         │
▼         ▼
Answer   Create plan
            │
            ▼
        Request approval
```

An agent workflow framework such as LangGraph can be introduced at this stage.

## Deliverable

A controlled agent workflow instead of an unrestricted chatbot loop.

---

# Phase 7 — Mutation Tools

**Goal:** Introduce carefully controlled Kubernetes modifications.

Start with:

```text
restart_pod()
```

Then add:

```text
scale_deployment()
```

Later:

```text
patch_deployment()
```

The LLM must never directly receive unrestricted Kubernetes or shell access.

Architecture:

```text
LLM
 │
 ▼
Tool request
 │
 ▼
Policy Engine
 │
 ├── Is the operation allowed?
 ├── Is the namespace allowed?
 ├── Are parameters valid?
 ├── What is the risk level?
 └── Is approval required?
 │
 ▼
Kubernetes API
```

## Deliverable

Controlled mutation capabilities.

---

# Phase 8 — Human Approval

**Goal:** Add human-in-the-loop control for mutations.

Example:

```text
User:
"Restart the failing backend pods."

Agent:

I found 2 failing pods.

Proposed action:

restart:
  namespace: backend
  pods:
    - backend-abc
    - backend-def

Reason:
Both are in CrashLoopBackOff.

[Approve] [Reject]
```

The mutation executes only after approval.

## Deliverable

A human-in-the-loop Kubernetes remediation agent.

---

# Phase 9 — Verification

**Goal:** Verify whether an action actually solved the problem.

Do not stop after:

```text
restart_pod()
```

Instead:

```text
Execute action
       │
       ▼
Wait
       │
       ▼
Inspect cluster again
       │
       ▼
Did it work?
       │
    ┌──┴───┐
   Yes     No
    │       │
    ▼       ▼
 Success   Diagnose further
```

Example result:

> Restarted the pods, but both entered CrashLoopBackOff again. The underlying issue appears to be a database connectivity problem.

## Deliverable

Closed-loop remediation: diagnose → act → verify.

---

# Phase 10 — Audit Logging

**Goal:** Record every important operation.

Suggested audit fields:

```text
audit_logs

id
timestamp
user
request
agent_reasoning_summary
tool
arguments
approval
result
duration
```

Example:

```text
User:
Fix backend

Agent:
Detected CrashLoopBackOff

Tool:
restart_pod

Approval:
Approved

Result:
Failed

Verification:
Pods still unhealthy
```

Do not log Secret contents, credentials, or unnecessary sensitive information.

## Deliverable

A complete audit trail for agent activity.

---

# Phase 11 — Security Hardening

**Goal:** Treat the project as a real infrastructure system.

## Authentication

```text
User
 ↓
Authentication
 ↓
FastAPI
```

## Authorization

Example capability model:

```text
Developer
   ├── Read cluster
   └── Restart development pods

DevOps
   ├── Read
   ├── Restart
   └── Scale

Admin
   └── Additional privileged actions
```

## Agent security

Protect against:

- Prompt injection
- Malicious tool arguments
- Privilege escalation
- Excessive agency
- Destructive actions
- Secrets leakage
- Runaway tool loops
- Excessive resource consumption

## Deliverable

A hardened authorization and safety model.

---

# Phase 12 — Containerize the Application

**Goal:** Package the application for deployment.

Create:

```text
Dockerfile
docker-compose.yaml
```

The application communicates with:

```text
FastAPI Agent
      │
      ├── LLM API
      │
      └── Kubernetes API
```

## Deliverable

A containerized application ready for Kubernetes deployment.

---

# Phase 13 — Deploy the Agent into Kubernetes

**Goal:** Run the agent inside the cluster.

Architecture:

```text
                    Kubernetes Cluster

             ┌──────────────────────────┐
             │                          │
             │   AI Agent Namespace     │
             │                          │
User ───────►│   ┌──────────────────┐   │
             │   │ FastAPI Agent    │   │
             │   └────────┬─────────┘   │
             │            │             │
             │       ServiceAccount     │
             │            │             │
             └────────────┼─────────────┘
                          │
                          ▼
                    Kubernetes API
```

Use in-cluster configuration:

```python
config.load_incluster_config()
```

instead of relying on a developer's local kubeconfig.

## Deliverable

The AI agent runs as a Kubernetes workload using a controlled ServiceAccount.

---

# Phase 14 — Observability

**Goal:** Monitor the agent itself.

Potential integrations:

- Prometheus
- Grafana
- Structured logging
- OpenTelemetry

Monitor:

- Request latency
- LLM latency
- Token usage
- Tool execution time
- Number of tool calls
- Failed actions
- Approval rate
- Remediation success rate

## Deliverable

Operational visibility into both the agent and its actions.

---

# Phase 15 — Advanced Capabilities

Add these only after the MVP is stable.

## Multi-cluster support

```text
Agent
 │
 ├── Development cluster
 ├── Staging cluster
 └── Production cluster
```

## Automatic remediation

For predefined and low-risk scenarios:

```text
Problem detected
       ↓
Diagnosis
       ↓
Known remediation
       ↓
Policy validation
       ↓
Automatic action
       ↓
Verification
```

## Incident mode

Example request:

> "Investigate why checkout is down."

Potential investigation:

```text
Deployment
 ↓
Pods
 ↓
Services
 ↓
Ingress
 ↓
Events
 ↓
Logs
 ↓
Dependencies
```

The agent can eventually generate an incident report containing findings, actions, and verification results.

---

# Final Architecture

```text
                           USER
                            │
                            ▼
                    ┌──────────────┐
                    │   FastAPI    │
                    │     API      │
                    └──────┬───────┘
                           │
                           ▼
                    ┌──────────────┐
                    │    Agent     │
                    │  /Workflow   │
                    └──────┬───────┘
                           │
                           ▼
                    ┌──────────────┐
                    │     LLM      │
                    └──────┬───────┘
                           │
                    Tool Calling
                           │
          ┌────────────────┼─────────────────┐
          │                │                 │
          ▼                ▼                 ▼
    Read Tools       Mutation Tools     Analysis Tools
          │                │                 │
          └────────────────┼─────────────────┘
                           │
                           ▼
                    ┌──────────────┐
                    │ Policy Engine│
                    └──────┬───────┘
                           │
                     Approval?
                       /     \
                     No       Yes
                     │         │
                     └────┬────┘
                          ▼
                  ┌───────────────┐
                  │ Kubernetes API│
                  └───────┬───────┘
                          │
                          ▼
                     Verification
                          │
                          ▼
                      Audit Log
```

---

# Development Milestones

| Milestone | Result |
|---|---|
| M1 | FastAPI application |
| M2 | FastAPI communicates with Kubernetes |
| M3 | Least-privilege Kubernetes RBAC |
| M4 | FastAPI communicates with an LLM |
| M5 | LLM calls Kubernetes read tools |
| M6 | Controlled diagnosis workflow |
| M7 | Controlled mutation tools |
| M8 | Human approval |
| M9 | Post-action verification |
| M10 | Audit logging and security |
| M11 | Agent deployed inside Kubernetes |
| M12 | Advanced and autonomous remediation |

---

# Recommended MVP Success Criteria

The first major proof of success is:

> A user asks a natural-language Kubernetes question → the LLM decides which approved Kubernetes tools to call → the tools inspect the real cluster → the LLM returns an evidence-based diagnosis.

After that, the project evolves through:

```text
Observability
      ↓
Diagnosis
      ↓
Proposed remediation
      ↓
Policy validation
      ↓
Human approval
      ↓
Execution
      ↓
Verification
      ↓
Audit logging
```

This progression should be followed incrementally. Do not begin with unrestricted autonomous Kubernetes modifications.
