import json

import pytest
from kubernetes.client import ApiException

from app.agent.tools import LOG_TAIL_CHARS, MAX_LIST_ITEMS, ToolRegistry
from app.config import Settings, settings
from app.schemas.kubernetes import (
    ContainerInfo,
    NamespaceListResponse,
    NodeDescribe,
    PodDescribe,
    PodInfo,
    PodListResponse,
)


class FakeK8s:
    def __init__(self):
        self.calls = []

    def _record(self, name, *args):
        self.calls.append((name,) + args)

    async def get_pods(self, namespace):
        self._record("get_pods", namespace)
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

    async def describe_pod(self, namespace, pod_name):
        self._record("describe_pod", namespace, pod_name)
        return PodDescribe(
            name=pod_name,
            namespace=namespace,
            phase="Running",
            conditions=["Ready=True"],
            init_containers=[],
            containers=[
                {
                    "name": "app",
                    "image": "backend:v2",
                    "state": "waiting",
                    "ready": False,
                    "restart_count": 5,
                    "waiting_reason": "CrashLoopBackOff",
                    "last_termination_reason": "OOMKilled",
                    "exit_code": 137,
                }
            ],
            volumes=[],
            owner_chain=["ReplicaSet/backend-abc", "Deployment/backend"],
        )

    async def describe_deployment(self, namespace, name):
        raise NotImplementedError

    async def get_namespaces(self):
        self._record("get_namespaces")
        return NamespaceListResponse(
            items=[
                {"name": "default", "phase": "Active"},
                {"name": "kube-system", "phase": "Active"},
            ]
        )

    async def get_endpoints(self, namespace, service_name):
        self._record("get_endpoints", namespace, service_name)
        from app.schemas.kubernetes import EndpointsInfo

        return EndpointsInfo(
            name=service_name,
            namespace=namespace,
            addresses=[],
            not_ready_addresses=[],
            ports=[],
        )

    async def get_pvcs(self, namespace):
        raise NotImplementedError

    async def get_nodes(self):
        raise NotImplementedError

    async def describe_node(self, node_name):
        self._record("describe_node", node_name)
        return NodeDescribe(
            name=node_name,
            ready=True,
            unschedulable=False,
            conditions=[{"type": "Ready", "status": "True"}],
            taints=[],
            allocatable={"cpu": "4"},
            capacity={"cpu": "4", "memory": "8Gi", "pods": "110"},
            addresses=["InternalIP=192.168.1.1"],
        )

    async def get_replicasets(self, namespace):
        raise NotImplementedError

    async def get_ingresses(self, namespace):
        raise NotImplementedError

    async def get_statefulsets(self, namespace):
        raise NotImplementedError

    async def get_daemonsets(self, namespace):
        raise NotImplementedError

    async def get_jobs(self, namespace):
        raise NotImplementedError

    async def get_cronjobs(self, namespace):
        raise NotImplementedError

    async def get_hpas(self, namespace):
        raise NotImplementedError


@pytest.fixture
def fake_k8s():
    return FakeK8s()


@pytest.fixture
def registry(fake_k8s):
    return ToolRegistry(fake_k8s, settings)


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


def test_definitions_cover_all_21_tools(registry):
    names = {d["name"] for d in registry.definitions()}

    assert names == {
        "get_pods",
        "get_deployments",
        "get_deployment",
        "get_services",
        "get_service",
        "get_pod_logs",
        "get_events",
        "describe_pod",
        "describe_deployment",
        "get_namespaces",
        "get_endpoints",
        "get_pvcs",
        "get_nodes",
        "describe_node",
        "get_replicasets",
        "get_ingresses",
        "get_statefulsets",
        "get_daemonsets",
        "get_jobs",
        "get_cronjobs",
        "get_hpas",
    }


def test_every_definition_has_a_handler(registry):
    defined = {d["name"] for d in registry.definitions()}

    assert defined == set(registry._handlers.keys())


# --- Phase 5.2 tools --------------------------------------------------------


@pytest.mark.asyncio
async def test_describe_pod_serializes_container_state(registry):
    result = json.loads(
        await registry.execute("describe_pod", {"namespace": "ns", "pod_name": "backend-abc"})
    )

    container = result["containers"][0]
    assert container["state"] == "waiting"
    assert container["waiting_reason"] == "CrashLoopBackOff"
    assert container["last_termination_reason"] == "OOMKilled"
    assert container["exit_code"] == 137
    assert result["owner_chain"] == ["ReplicaSet/backend-abc", "Deployment/backend"]


@pytest.mark.asyncio
async def test_cluster_scoped_tool_receives_no_injected_namespace(registry, fake_k8s):
    await registry.execute("get_namespaces", {})

    assert ("get_namespaces",) in fake_k8s.calls


@pytest.mark.asyncio
async def test_cluster_scoped_tool_ignores_stray_namespace_argument(registry, fake_k8s):
    result = json.loads(await registry.execute("describe_node", {"node_name": "node-1", "namespace": "ns"}))

    assert result["name"] == "node-1"
    assert ("describe_node", "node-1") in fake_k8s.calls


@pytest.mark.asyncio
async def test_invalid_service_name_rejected(registry):
    result = json.loads(
        await registry.execute(
            "get_endpoints", {"namespace": "ns", "service_name": "Bad Service!"}
        )
    )

    assert "Invalid service_name" in result["error"]


@pytest.mark.asyncio
async def test_invalid_node_name_rejected(registry):
    result = json.loads(
        await registry.execute("describe_node", {"node_name": "-bad-node-"})
    )

    assert "Invalid node_name" in result["error"]


@pytest.mark.asyncio
async def test_empty_endpoints_serialize(registry):
    result = json.loads(
        await registry.execute("get_endpoints", {"namespace": "ns", "service_name": "svc"})
    )

    assert result["addresses"] == []
