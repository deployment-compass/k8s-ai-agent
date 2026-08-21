import json

import pytest
from kubernetes.client import ApiException

from app.agent.tools import LOG_TAIL_CHARS, MAX_LIST_ITEMS, ToolRegistry
from app.config import Settings, settings
from app.schemas.kubernetes import PodInfo, PodListResponse


class FakeK8s:
    def __init__(self):
        self.calls = []

    async def get_pods(self, namespace):
        self.calls.append(("get_pods", namespace))
        return PodListResponse(
            items=[
                PodInfo(
                    name="backend-abc",
                    namespace=namespace,
                    status="Running",
                    ready=True,
                    restart_count=0,
                )
            ]
        )

    async def get_deployments(self, namespace):
        raise NotImplementedError

    async def get_deployment(self, namespace, name):
        raise NotImplementedError

    async def get_services(self, namespace):
        raise NotImplementedError

    async def get_service(self, namespace, name):
        raise NotImplementedError

    async def get_pod_logs(self, namespace, pod_name):
        return "x" * (LOG_TAIL_CHARS + 500)

    async def get_events(self, namespace):
        return [
            PodInfo(  # any pydantic model works for capping test
                name=f"e{i}",
                namespace=namespace,
                status="Normal",
                ready=False,
                restart_count=0,
            )
            for i in range(MAX_LIST_ITEMS + 10)
        ]


@pytest.fixture
def registry():
    return ToolRegistry(FakeK8s(), settings)


@pytest.mark.asyncio
async def test_unknown_tool_returns_error(registry):
    result = json.loads(await registry.execute("delete_namespace", {}))

    assert "error" in result
    assert "Unknown tool" in result["error"]


@pytest.mark.asyncio
async def test_missing_required_parameter(registry):
    result = json.loads(await registry.execute("get_pod_logs", {"namespace": "default"}))

    assert "Missing required parameter 'pod_name'" in result["error"]


@pytest.mark.asyncio
async def test_invalid_namespace_rejected(registry):
    result = json.loads(
        await registry.execute("get_pods", {"namespace": "Bad Namespace!"})
    )

    assert "Invalid namespace" in result["error"]


@pytest.mark.asyncio
async def test_default_namespace_applied_when_missing(registry, monkeypatch):
    monkeypatch.setattr(settings, "default_namespace", "kube-system")

    result = json.loads(await registry.execute("get_pods", {}))

    assert result["items"][0]["namespace"] == "kube-system"


@pytest.mark.asyncio
async def test_successful_execution_serializes_models(registry):
    result = json.loads(await registry.execute("get_pods", {"namespace": "backend"}))

    assert result["items"][0]["name"] == "backend-abc"
    assert result["items"][0]["ready"] is True


@pytest.mark.asyncio
async def test_logs_truncated_to_tail(registry):
    result = json.loads(await registry.execute("get_pod_logs", {"namespace": "ns", "pod_name": "p"}))

    assert len(result["logs"]) < LOG_TAIL_CHARS + 200
    assert "truncated" in result["logs"]


@pytest.mark.asyncio
async def test_lists_capped(registry):
    result = json.loads(await registry.execute("get_events", {"namespace": "ns"}))

    assert len(result["items"]) == MAX_LIST_ITEMS
    assert "Showing first" in result["note"]


@pytest.mark.asyncio
async def test_api_exception_captured_as_error():
    class FailingK8s(FakeK8s):
        async def get_pods(self, namespace):
            raise ApiException(status=403, reason="Forbidden")

    registry = ToolRegistry(FailingK8s(), settings)
    result = json.loads(await registry.execute("get_pods", {"namespace": "backend"}))

    assert result["error"] == "Kubernetes API error 403: Forbidden"


def test_definitions_cover_all_seven_tools(registry):
    names = {d["name"] for d in registry.definitions()}

    assert names == {
        "get_pods",
        "get_deployments",
        "get_deployment",
        "get_services",
        "get_service",
        "get_pod_logs",
        "get_events",
    }
