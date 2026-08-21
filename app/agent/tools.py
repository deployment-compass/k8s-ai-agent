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

        namespace = arguments.get("namespace")
        if namespace is None:
            arguments["namespace"] = self._settings.default_namespace
        elif error := _validate_name("namespace", namespace):
            return error

        for field_name in definition.parameters.get("required", []):
            if field_name not in arguments or not isinstance(arguments[field_name], str):
                return f"Missing required parameter '{field_name}'."

        for field_name in ("name", "pod_name"):
            if field_name in arguments:
                if error := _validate_name(field_name, arguments[field_name]):
                    return error

        return None
