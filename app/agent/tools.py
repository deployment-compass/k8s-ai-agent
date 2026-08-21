import json
import logging
import re
import time
from dataclasses import dataclass

from kubernetes.client import ApiException

from app.config import Settings
from app.kubernetes.client import KubernetesClient

logger = logging.getLogger(__name__)

DNS_1123_PATTERN = re.compile(r"^[a-z0-9]([-a-z0-9]*[a-z0-9])?$")
MAX_NAME_LENGTH = 253
LOG_TAIL_CHARS = 8000
MAX_LIST_ITEMS = 100
RESULT_PREVIEW_CHARS = 200


@dataclass(frozen=True)
class ToolDefinition:
    name: str
    description: str
    parameters: dict


TOOL_DEFINITIONS: list[ToolDefinition] = [
    ToolDefinition(
        name="get_pods",
        description="List all pods in a namespace with status, readiness, restart count, node, and creation time.",
        parameters={
            "type": "object",
            "properties": {
                "namespace": {"type": "string", "description": "Kubernetes namespace"},
            },
            "required": ["namespace"],
        },
    ),
    ToolDefinition(
        name="get_deployments",
        description="List all deployments in a namespace with replica counts and conditions.",
        parameters={
            "type": "object",
            "properties": {
                "namespace": {"type": "string", "description": "Kubernetes namespace"},
            },
            "required": ["namespace"],
        },
    ),
    ToolDefinition(
        name="get_deployment",
        description="Get a single deployment by name with replica counts and conditions.",
        parameters={
            "type": "object",
            "properties": {
                "namespace": {"type": "string", "description": "Kubernetes namespace"},
                "name": {"type": "string", "description": "Deployment name"},
            },
            "required": ["namespace", "name"],
        },
    ),
    ToolDefinition(
        name="get_services",
        description="List all services in a namespace with type, cluster IP, and ports.",
        parameters={
            "type": "object",
            "properties": {
                "namespace": {"type": "string", "description": "Kubernetes namespace"},
            },
            "required": ["namespace"],
        },
    ),
    ToolDefinition(
        name="get_service",
        description="Get a single service by name with type, cluster IP, and ports.",
        parameters={
            "type": "object",
            "properties": {
                "namespace": {"type": "string", "description": "Kubernetes namespace"},
                "name": {"type": "string", "description": "Service name"},
            },
            "required": ["namespace", "name"],
        },
    ),
    ToolDefinition(
        name="get_pod_logs",
        description="Get the recent logs of a single pod.",
        parameters={
            "type": "object",
            "properties": {
                "namespace": {"type": "string", "description": "Kubernetes namespace"},
                "pod_name": {"type": "string", "description": "Pod name"},
            },
            "required": ["namespace", "pod_name"],
        },
    ),
    ToolDefinition(
        name="get_events",
        description="List recent Kubernetes events in a namespace (warnings, scheduling failures, image pull errors, etc.).",
        parameters={
            "type": "object",
            "properties": {
                "namespace": {"type": "string", "description": "Kubernetes namespace"},
            },
            "required": ["namespace"],
        },
    ),
    # --- Phase 5.2: expanded diagnostics ---
    ToolDefinition(
        name="describe_pod",
        description=(
            "Deep inspection of a single pod: per-container state (running/waiting/terminated), "
            "waiting reasons (CrashLoopBackOff, ImagePullBackOff), last termination reason "
            "(e.g. OOMKilled), exit codes, restarts, probes, resource requests/limits, volumes, "
            "and owner chain. Use this to find out WHY a pod is unhealthy."
        ),
        parameters={
            "type": "object",
            "properties": {
                "namespace": {"type": "string", "description": "Kubernetes namespace"},
                "pod_name": {"type": "string", "description": "Pod name"},
            },
            "required": ["namespace", "pod_name"],
        },
    ),
    ToolDefinition(
        name="describe_deployment",
        description=(
            "Deep inspection of a deployment: rollout strategy, conditions with reasons and "
            "messages, container images, and owned ReplicaSets with revisions for rollout tracing."
        ),
        parameters={
            "type": "object",
            "properties": {
                "namespace": {"type": "string", "description": "Kubernetes namespace"},
                "name": {"type": "string", "description": "Deployment name"},
            },
            "required": ["namespace", "name"],
        },
    ),
    ToolDefinition(
        name="get_namespaces",
        description="List namespaces in the cluster with phase and creation time.",
        parameters={
            "type": "object",
            "properties": {},
            "required": [],
        },
    ),
    ToolDefinition(
        name="get_endpoints",
        description=(
            "Get the backend pod IPs and ports behind a service. Empty addresses usually mean "
            "a selector mismatch or no ready pods backing the service."
        ),
        parameters={
            "type": "object",
            "properties": {
                "namespace": {"type": "string", "description": "Kubernetes namespace"},
                "service_name": {"type": "string", "description": "Service name"},
            },
            "required": ["namespace", "service_name"],
        },
    ),
    ToolDefinition(
        name="get_pvcs",
        description=(
            "List persistent volume claims in a namespace with binding phase, capacity, and "
            "storage class. Pending claims can block pods that mount them."
        ),
        parameters={
            "type": "object",
            "properties": {
                "namespace": {"type": "string", "description": "Kubernetes namespace"},
            },
            "required": ["namespace"],
        },
    ),
    ToolDefinition(
        name="get_nodes",
        description="List cluster nodes with Ready condition and kubelet version.",
        parameters={
            "type": "object",
            "properties": {},
            "required": [],
        },
    ),
    ToolDefinition(
        name="describe_node",
        description=(
            "Deep inspection of a node: pressure/scheduling conditions, taints, allocatable vs "
            "capacity for CPU/memory/pods, and addresses."
        ),
        parameters={
            "type": "object",
            "properties": {
                "node_name": {"type": "string", "description": "Node name"},
            },
            "required": ["node_name"],
        },
    ),
    ToolDefinition(
        name="get_replicasets",
        description=(
            "List ReplicaSets in a namespace with desired/ready replicas, revision, and owning "
            "deployment, for rollout history tracing."
        ),
        parameters={
            "type": "object",
            "properties": {
                "namespace": {"type": "string", "description": "Kubernetes namespace"},
            },
            "required": ["namespace"],
        },
    ),
    ToolDefinition(
        name="get_ingresses",
        description="List ingresses in a namespace with hosts, routing rules (path to service), and TLS hosts.",
        parameters={
            "type": "object",
            "properties": {
                "namespace": {"type": "string", "description": "Kubernetes namespace"},
            },
            "required": ["namespace"],
        },
    ),
    ToolDefinition(
        name="get_statefulsets",
        description="List statefulsets in a namespace with replica counts and conditions.",
        parameters={
            "type": "object",
            "properties": {
                "namespace": {"type": "string", "description": "Kubernetes namespace"},
            },
            "required": ["namespace"],
        },
    ),
    ToolDefinition(
        name="get_daemonsets",
        description="List daemonsets in a namespace with desired/ready/available scheduled pod counts.",
        parameters={
            "type": "object",
            "properties": {
                "namespace": {"type": "string", "description": "Kubernetes namespace"},
            },
            "required": ["namespace"],
        },
    ),
    ToolDefinition(
        name="get_jobs",
        description=(
            "List jobs in a namespace with active/succeeded/failed status, completions, "
            "and start time."
        ),
        parameters={
            "type": "object",
            "properties": {
                "namespace": {"type": "string", "description": "Kubernetes namespace"},
            },
            "required": ["namespace"],
        },
    ),
    ToolDefinition(
        name="get_cronjobs",
        description="List cronjobs in a namespace with schedule, suspension state, active count, and last schedule time.",
        parameters={
            "type": "object",
            "properties": {
                "namespace": {"type": "string", "description": "Kubernetes namespace"},
            },
            "required": ["namespace"],
        },
    ),
    ToolDefinition(
        name="get_hpas",
        description=(
            "List horizontal pod autoscalers in a namespace with scale target, min/max/current/"
            "desired replicas, and CPU utilization target vs current."
        ),
        parameters={
            "type": "object",
            "properties": {
                "namespace": {"type": "string", "description": "Kubernetes namespace"},
            },
            "required": ["namespace"],
        },
    ),
]


def _validate_name(field: str, value: str) -> str | None:
    if not value or len(value) > MAX_NAME_LENGTH or not DNS_1123_PATTERN.match(value):
        return (
            f"Invalid {field}: '{value[:100]}'. "
            "Must be a lowercase DNS-1123 label (alphanumerics and hyphens)."
        )
    return None


def _serialize_result(result) -> str:
    if isinstance(result, str):
        if len(result) > LOG_TAIL_CHARS:
            result = (
                f"[...truncated, showing last {LOG_TAIL_CHARS} characters...]\n"
                f"{result[-LOG_TAIL_CHARS:]}"
            )
        return json.dumps({"logs": result})

    if isinstance(result, list):
        truncated = [item.model_dump(mode="json") for item in result[:MAX_LIST_ITEMS]]
        payload: dict = {"items": truncated, "count": len(result)}
        if len(result) > MAX_LIST_ITEMS:
            payload["note"] = f"Showing first {MAX_LIST_ITEMS} of {len(result)} items."
        return json.dumps(payload)

    return json.dumps(result.model_dump(mode="json"))


class ToolRegistry:
    """Binds tool definitions to a KubernetesClient and executes them safely."""

    def __init__(self, k8s_client: KubernetesClient, settings: Settings):
        self._k8s = k8s_client
        self._settings = settings
        self._handlers = {
            "get_pods": self._k8s.get_pods,
            "get_deployments": self._k8s.get_deployments,
            "get_deployment": self._k8s.get_deployment,
            "get_services": self._k8s.get_services,
            "get_service": self._k8s.get_service,
            "get_pod_logs": self._k8s.get_pod_logs,
            "get_events": self._k8s.get_events,
            "describe_pod": self._k8s.describe_pod,
            "describe_deployment": self._k8s.describe_deployment,
            "get_namespaces": self._k8s.get_namespaces,
            "get_endpoints": self._k8s.get_endpoints,
            "get_pvcs": self._k8s.get_pvcs,
            "get_nodes": self._k8s.get_nodes,
            "describe_node": self._k8s.describe_node,
            "get_replicasets": self._k8s.get_replicasets,
            "get_ingresses": self._k8s.get_ingresses,
            "get_statefulsets": self._k8s.get_statefulsets,
            "get_daemonsets": self._k8s.get_daemonsets,
            "get_jobs": self._k8s.get_jobs,
            "get_cronjobs": self._k8s.get_cronjobs,
            "get_hpas": self._k8s.get_hpas,
        }

    def definitions(self) -> list[dict]:
        return [
            {
                "name": d.name,
                "description": d.description,
                "parameters": d.parameters,
            }
            for d in TOOL_DEFINITIONS
        ]

    def known_tools(self) -> str:
        return ", ".join(sorted(self._handlers))

    async def execute(self, name: str, arguments: dict) -> str:
        handler = self._handlers.get(name)
        if handler is None:
            logger.warning("Tool call rejected: unknown tool '%s'", name)
            return json.dumps(
                {"error": f"Unknown tool '{name}'. Valid tools: {self.known_tools()}"}
            )

        arguments = arguments if isinstance(arguments, dict) else {}
        definition = next(d for d in TOOL_DEFINITIONS if d.name == name)
        allowed = set(definition.parameters.get("properties", {}).keys())
        arguments = {k: v for k, v in arguments.items() if k in allowed}
        error = self._validate_arguments(name, arguments)
        if error:
            logger.warning("Tool call rejected: %s args=%s", name, arguments)
            return json.dumps({"error": error})

        logger.info("Tool call: %s args=%s", name, arguments)
        started = time.perf_counter()
        try:
            result = await handler(**arguments)
            serialized = _serialize_result(result)
            logger.info(
                "Tool result: %s status=ok size=%d duration=%.3fs",
                name,
                len(serialized),
                time.perf_counter() - started,
            )
            logger.debug("Tool result preview: %s: %s", name, serialized[:RESULT_PREVIEW_CHARS])
            return serialized
        except ApiException as exc:
            reason = exc.reason or "request failed"
            message = f"Kubernetes API error {exc.status}: {reason}"
            logger.warning(
                "Tool result: %s status=error duration=%.3fs error=%s",
                name,
                time.perf_counter() - started,
                message,
            )
            return json.dumps({"error": message})
        except Exception as exc:
            logger.warning(
                "Tool result: %s status=error duration=%.3fs error=%s: %s",
                name,
                time.perf_counter() - started,
                type(exc).__name__,
                exc,
            )
            return json.dumps({"error": f"Tool execution failed: {exc}"})

    def _validate_arguments(self, name: str, arguments: dict) -> str | None:
        definition = next(d for d in TOOL_DEFINITIONS if d.name == name)
        properties = definition.parameters.get("properties", {})

        if "namespace" in properties:
            namespace = arguments.get("namespace")
            if namespace is None:
                arguments["namespace"] = self._settings.default_namespace
            elif error := _validate_name("namespace", namespace):
                return error

        for field_name in definition.parameters.get("required", []):
            if field_name not in arguments or not isinstance(arguments[field_name], str):
                return f"Missing required parameter '{field_name}'."

        for field_name in ("name", "pod_name", "service_name", "node_name"):
            if field_name in arguments:
                if error := _validate_name(field_name, arguments[field_name]):
                    return error

        return None
