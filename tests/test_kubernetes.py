from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from httpx import ASGITransport, AsyncClient

from app.main import app
from app.schemas.kubernetes import (
    CronJobInfo,
    CronJobListResponse,
    DaemonSetInfo,
    DaemonSetListResponse,
    DeploymentDescribe,
    DeploymentInfo,
    DeploymentListResponse,
    EndpointsInfo,
    EventInfo,
    HPAInfo,
    HPAListResponse,
    IngressInfo,
    IngressListResponse,
    JobInfo,
    JobListResponse,
    NamespaceInfo,
    NamespaceListResponse,
    NodeDescribe,
    NodeInfo,
    NodeListResponse,
    PVCInfo,
    PVCListResponse,
    PodDescribe,
    PodInfo,
    PodListResponse,
    ReplicaSetInfo,
    ReplicaSetListResponse,
    ServiceInfo,
    ServiceListResponse,
    StatefulSetInfo,
    StatefulSetListResponse,
)


@pytest.fixture
def mock_k8s_client():
    with patch("app.api.v1.kubernetes.KubernetesClient") as mock:
        yield mock


@pytest.mark.asyncio
async def test_get_pods(mock_k8s_client):
    mock_instance = MagicMock()
    mock_instance.get_pods = AsyncMock(
        return_value=PodListResponse(
            items=[
                PodInfo(
                    name="test-pod",
                    namespace="default",
                    status="Running",
                    ready=True,
                    restart_count=0,
                    node="minikube",
                    created_at="2024-01-01T00:00:00Z",
                )
            ]
        )
    )
    mock_k8s_client.return_value = mock_instance

    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as client:
        response = await client.get(
            "/api/v1/clusters/default/namespaces/default/pods"
        )

    assert response.status_code == 200
    data = response.json()
    assert len(data["items"]) == 1
    assert data["items"][0]["name"] == "test-pod"
    mock_instance.get_pods.assert_called_once_with("default")


@pytest.mark.asyncio
async def test_get_deployments(mock_k8s_client):
    mock_instance = MagicMock()
    mock_instance.get_deployments = AsyncMock(
        return_value=DeploymentListResponse(
            items=[
                DeploymentInfo(
                    name="test-deploy",
                    namespace="default",
                    replicas=3,
                    ready_replicas=3,
                    updated_replicas=3,
                    available_replicas=3,
                    conditions=["Ready=True"],
                )
            ]
        )
    )
    mock_k8s_client.return_value = mock_instance

    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as client:
        response = await client.get(
            "/api/v1/clusters/default/namespaces/default/deployments"
        )

    assert response.status_code == 200
    data = response.json()
    assert len(data["items"]) == 1
    assert data["items"][0]["name"] == "test-deploy"
    mock_instance.get_deployments.assert_called_once_with("default")


@pytest.mark.asyncio
async def test_get_deployment(mock_k8s_client):
    mock_instance = MagicMock()
    mock_instance.get_deployment = AsyncMock(
        return_value=DeploymentInfo(
            name="test-deploy",
            namespace="default",
            replicas=3,
            ready_replicas=3,
            updated_replicas=3,
            available_replicas=3,
            conditions=["Ready=True"],
        )
    )
    mock_k8s_client.return_value = mock_instance

    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as client:
        response = await client.get(
            "/api/v1/clusters/default/namespaces/default/deployments/test-deploy"
        )

    assert response.status_code == 200
    data = response.json()
    assert data["name"] == "test-deploy"
    assert data["replicas"] == 3
    mock_instance.get_deployment.assert_called_once_with("default", "test-deploy")


@pytest.mark.asyncio
async def test_get_service(mock_k8s_client):
    mock_instance = MagicMock()
    mock_instance.get_service = AsyncMock(
        return_value=ServiceInfo(
            name="test-svc",
            namespace="default",
            type="ClusterIP",
            cluster_ip="10.0.0.1",
            ports=["80/TCP -> 8080"],
        )
    )
    mock_k8s_client.return_value = mock_instance

    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as client:
        response = await client.get(
            "/api/v1/clusters/default/namespaces/default/services/test-svc"
        )

    assert response.status_code == 200
    data = response.json()
    assert data["name"] == "test-svc"
    assert data["type"] == "ClusterIP"
    mock_instance.get_service.assert_called_once_with("default", "test-svc")


@pytest.mark.asyncio
async def test_get_services(mock_k8s_client):
    mock_instance = MagicMock()
    mock_instance.get_services = AsyncMock(
        return_value=ServiceListResponse(
            items=[
                ServiceInfo(
                    name="test-svc",
                    namespace="default",
                    type="ClusterIP",
                    cluster_ip="10.0.0.1",
                    ports=["80/TCP -> 8080"],
                )
            ]
        )
    )
    mock_k8s_client.return_value = mock_instance

    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as client:
        response = await client.get(
            "/api/v1/clusters/default/namespaces/default/services"
        )

    assert response.status_code == 200
    data = response.json()
    assert len(data["items"]) == 1
    assert data["items"][0]["name"] == "test-svc"
    mock_instance.get_services.assert_called_once_with("default")


@pytest.mark.asyncio
async def test_get_pod_logs(mock_k8s_client):
    mock_instance = MagicMock()
    mock_instance.get_pod_logs = AsyncMock(return_value="log line 1\nlog line 2")
    mock_k8s_client.return_value = mock_instance

    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as client:
        response = await client.get(
            "/api/v1/clusters/default/namespaces/default/pods/test-pod/logs"
        )

    assert response.status_code == 200
    mock_instance.get_pod_logs.assert_called_once_with("default", "test-pod")


@pytest.mark.asyncio
async def test_get_events(mock_k8s_client):
    mock_instance = MagicMock()
    mock_instance.get_events = AsyncMock(return_value=[])
    mock_k8s_client.return_value = mock_instance

    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as client:
        response = await client.get(
            "/api/v1/clusters/default/namespaces/default/events"
        )

    assert response.status_code == 200
    mock_instance.get_events.assert_called_once_with("default")


@pytest.mark.asyncio
async def test_k8s_error_404(mock_k8s_client):
    from kubernetes.client.rest import ApiException

    mock_instance = MagicMock()
    mock_instance.get_pods = AsyncMock(
        side_effect=ApiException(status=404, reason="Not Found")
    )
    mock_k8s_client.return_value = mock_instance

    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as client:
        response = await client.get(
            "/api/v1/clusters/default/namespaces/nonexistent/pods"
        )

    assert response.status_code == 404


@pytest.mark.asyncio
async def test_k8s_error_403(mock_k8s_client):
    from kubernetes.client.rest import ApiException

    mock_instance = MagicMock()
    mock_instance.get_pods = AsyncMock(
        side_effect=ApiException(status=403, reason="Forbidden")
    )
    mock_k8s_client.return_value = mock_instance

    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as client:
        response = await client.get(
            "/api/v1/clusters/default/namespaces/default/pods"
        )

    assert response.status_code == 403


# --- Phase 5.2: expanded diagnostics endpoints ------------------------------


@pytest.mark.asyncio
async def test_get_namespaces(mock_k8s_client):
    mock_instance = MagicMock()
    mock_instance.get_namespaces = AsyncMock(
        return_value=NamespaceListResponse(
            items=[NamespaceInfo(name="default", phase="Active")]
        )
    )
    mock_k8s_client.return_value = mock_instance

    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as client:
        response = await client.get("/api/v1/clusters/default/namespaces")

    assert response.status_code == 200
    data = response.json()
    assert data["items"][0]["name"] == "default"
    mock_instance.get_namespaces.assert_called_once_with()


@pytest.mark.asyncio
async def test_get_nodes(mock_k8s_client):
    mock_instance = MagicMock()
    mock_instance.get_nodes = AsyncMock(
        return_value=NodeListResponse(
            items=[NodeInfo(name="minikube", ready=True, kubelet_version="v1.30.0")]
        )
    )
    mock_k8s_client.return_value = mock_instance

    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as client:
        response = await client.get("/api/v1/clusters/default/nodes")

    assert response.status_code == 200
    data = response.json()
    assert data["items"][0]["name"] == "minikube"
    mock_instance.get_nodes.assert_called_once_with()


@pytest.mark.asyncio
async def test_describe_node(mock_k8s_client):
    mock_instance = MagicMock()
    mock_instance.describe_node = AsyncMock(
        return_value=NodeDescribe(
            name="minikube",
            ready=True,
            unschedulable=False,
            conditions=[{"type": "Ready", "status": "True"}],
            taints=[],
            allocatable={"cpu": "4"},
            capacity={"cpu": "4", "memory": "8Gi", "pods": "110"},
            addresses=["InternalIP=192.168.1.1"],
        )
    )
    mock_k8s_client.return_value = mock_instance

    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as client:
        response = await client.get(
            "/api/v1/clusters/default/nodes/minikube/describe"
        )

    assert response.status_code == 200
    data = response.json()
    assert data["name"] == "minikube"
    assert data["allocatable"]["cpu"] == "4"
    mock_instance.describe_node.assert_called_once_with("minikube")


@pytest.mark.asyncio
async def test_describe_pod(mock_k8s_client):
    mock_instance = MagicMock()
    mock_instance.describe_pod = AsyncMock(
        return_value=PodDescribe(
            name="backend-abc",
            namespace="default",
            phase="Running",
            conditions=["Ready=True"],
            init_containers=[],
            containers=[
                {
                    "name": "app",
                    "image": "backend:v2",
                    "state": "waiting",
                    "waiting_reason": "CrashLoopBackOff",
                    "last_termination_reason": "OOMKilled",
                    "exit_code": 137,
                    "restart_count": 5,
                }
            ],
            volumes=[{"name": "data", "type": "emptyDir"}],
            owner_chain=["ReplicaSet/backend-abc", "Deployment/backend"],
        )
    )
    mock_k8s_client.return_value = mock_instance

    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as client:
        response = await client.get(
            "/api/v1/clusters/default/namespaces/default/pods/backend-abc/describe"
        )

    assert response.status_code == 200
    data = response.json()
    container = data["containers"][0]
    assert container["waiting_reason"] == "CrashLoopBackOff"
    assert container["last_termination_reason"] == "OOMKilled"
    assert data["owner_chain"][-1] == "Deployment/backend"
    mock_instance.describe_pod.assert_called_once_with("default", "backend-abc")


@pytest.mark.asyncio
async def test_describe_deployment(mock_k8s_client):
    mock_instance = MagicMock()
    mock_instance.describe_deployment = AsyncMock(
        return_value=DeploymentDescribe(
            name="backend",
            namespace="default",
            replicas=3,
            ready_replicas=2,
            updated_replicas=3,
            available_replicas=2,
            strategy="RollingUpdate",
            max_surge="25%",
            max_unavailable="25%",
            selector={"app": "backend"},
            conditions=[
                {
                    "type": "Available",
                    "status": "False",
                    "reason": "MinimumReplicasUnavailable",
                    "message": "Deployment does not have minimum availability.",
                }
            ],
            images=["backend:v2"],
            owned_replicasets=[
                {"name": "backend-v2", "desired": 3, "ready": 2, "revision": "3"}
            ],
        )
    )
    mock_k8s_client.return_value = mock_instance

    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as client:
        response = await client.get(
            "/api/v1/clusters/default/namespaces/default/deployments/backend/describe"
        )

    assert response.status_code == 200
    data = response.json()
    assert data["strategy"] == "RollingUpdate"
    assert data["conditions"][0]["reason"] == "MinimumReplicasUnavailable"
    assert data["owned_replicasets"][0]["revision"] == "3"
    mock_instance.describe_deployment.assert_called_once_with("default", "backend")


@pytest.mark.asyncio
async def test_get_endpoints(mock_k8s_client):
    mock_instance = MagicMock()
    mock_instance.get_endpoints = AsyncMock(
        return_value=EndpointsInfo(
            name="backend-svc",
            namespace="default",
            addresses=["10.244.0.5"],
            not_ready_addresses=[],
            ports=[
                {"port": 80, "protocol": "TCP", "name": None}
            ],
        )
    )
    mock_k8s_client.return_value = mock_instance

    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as client:
        response = await client.get(
            "/api/v1/clusters/default/namespaces/default/services/backend-svc/endpoints"
        )

    assert response.status_code == 200
    data = response.json()
    assert data["addresses"] == ["10.244.0.5"]
    mock_instance.get_endpoints.assert_called_once_with("default", "backend-svc")


@pytest.mark.asyncio
async def test_get_pvcs(mock_k8s_client):
    mock_instance = MagicMock()
    mock_instance.get_pvcs = AsyncMock(
        return_value=PVCListResponse(
            items=[
                PVCInfo(
                    name="data-claim",
                    namespace="default",
                    phase="Pending",
                    storage_class="standard",
                )
            ]
        )
    )
    mock_k8s_client.return_value = mock_instance

    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as client:
        response = await client.get(
            "/api/v1/clusters/default/namespaces/default/pvcs"
        )

    assert response.status_code == 200
    data = response.json()
    assert data["items"][0]["phase"] == "Pending"
    mock_instance.get_pvcs.assert_called_once_with("default")


@pytest.mark.asyncio
async def test_get_replicasets(mock_k8s_client):
    mock_instance = MagicMock()
    mock_instance.get_replicasets = AsyncMock(
        return_value=ReplicaSetListResponse(
            items=[
                ReplicaSetInfo(
                    name="backend-v1",
                    namespace="default",
                    desired=0,
                    ready=0,
                    revision="1",
                    owner_deployment="backend",
                )
            ]
        )
    )
    mock_k8s_client.return_value = mock_instance

    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as client:
        response = await client.get(
            "/api/v1/clusters/default/namespaces/default/replicasets"
        )

    assert response.status_code == 200
    data = response.json()
    assert data["items"][0]["owner_deployment"] == "backend"
    mock_instance.get_replicasets.assert_called_once_with("default")


@pytest.mark.asyncio
async def test_get_ingresses(mock_k8s_client):
    mock_instance = MagicMock()
    mock_instance.get_ingresses = AsyncMock(
        return_value=IngressListResponse(
            items=[
                IngressInfo(
                    name="main",
                    namespace="default",
                    rules=[
                        {
                            "host": "app.example.com",
                            "paths": [
                                {"path": "/", "service_name": "frontend", "service_port": 80}
                            ],
                        }
                    ],
                    tls_hosts=["app.example.com"],
                )
            ]
        )
    )
    mock_k8s_client.return_value = mock_instance

    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as client:
        response = await client.get(
            "/api/v1/clusters/default/namespaces/default/ingresses"
        )

    assert response.status_code == 200
    data = response.json()
    assert data["items"][0]["rules"][0]["host"] == "app.example.com"
    assert data["items"][0]["tls_hosts"] == ["app.example.com"]
    mock_instance.get_ingresses.assert_called_once_with("default")


@pytest.mark.asyncio
async def test_get_statefulsets(mock_k8s_client):
    mock_instance = MagicMock()
    mock_instance.get_statefulsets = AsyncMock(
        return_value=StatefulSetListResponse(
            items=[
                StatefulSetInfo(
                    name="db",
                    namespace="default",
                    replicas=3,
                    ready_replicas=2,
                    updated_replicas=3,
                    conditions=[],
                )
            ]
        )
    )
    mock_k8s_client.return_value = mock_instance

    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as client:
        response = await client.get(
            "/api/v1/clusters/default/namespaces/default/statefulsets"
        )

    assert response.status_code == 200
    data = response.json()
    assert data["items"][0]["ready_replicas"] == 2
    mock_instance.get_statefulsets.assert_called_once_with("default")


@pytest.mark.asyncio
async def test_get_daemonsets(mock_k8s_client):
    mock_instance = MagicMock()
    mock_instance.get_daemonsets = AsyncMock(
        return_value=DaemonSetListResponse(
            items=[
                DaemonSetInfo(
                    name="node-agent",
                    namespace="default",
                    desired_scheduled=3,
                    ready=2,
                    available=2,
                    updated=3,
                )
            ]
        )
    )
    mock_k8s_client.return_value = mock_instance

    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as client:
        response = await client.get(
            "/api/v1/clusters/default/namespaces/default/daemonsets"
        )

    assert response.status_code == 200
    data = response.json()
    assert data["items"][0]["desired_scheduled"] == 3
    assert data["items"][0]["ready"] == 2
    mock_instance.get_daemonsets.assert_called_once_with("default")


@pytest.mark.asyncio
async def test_get_jobs(mock_k8s_client):
    mock_instance = MagicMock()
    mock_instance.get_jobs = AsyncMock(
        return_value=JobListResponse(
            items=[
                JobInfo(
                    name="migrate",
                    namespace="default",
                    active=1,
                    succeeded=0,
                    failed=0,
                    completions=1,
                    start_time="2026-08-21T00:00:00Z",
                )
            ]
        )
    )
    mock_k8s_client.return_value = mock_instance

    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as client:
        response = await client.get(
            "/api/v1/clusters/default/namespaces/default/jobs"
        )

    assert response.status_code == 200
    data = response.json()
    assert data["items"][0]["active"] == 1
    mock_instance.get_jobs.assert_called_once_with("default")


@pytest.mark.asyncio
async def test_get_cronjobs(mock_k8s_client):
    mock_instance = MagicMock()
    mock_instance.get_cronjobs = AsyncMock(
        return_value=CronJobListResponse(
            items=[
                CronJobInfo(
                    name="nightly-report",
                    namespace="default",
                    schedule="0 2 * * *",
                    suspend=False,
                    active_jobs=0,
                    last_schedule_time="2026-08-21T02:00:00Z",
                )
            ]
        )
    )
    mock_k8s_client.return_value = mock_instance

    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as client:
        response = await client.get(
            "/api/v1/clusters/default/namespaces/default/cronjobs"
        )

    assert response.status_code == 200
    data = response.json()
    assert data["items"][0]["schedule"] == "0 2 * * *"
    mock_instance.get_cronjobs.assert_called_once_with("default")


@pytest.mark.asyncio
async def test_get_hpas(mock_k8s_client):
    mock_instance = MagicMock()
    mock_instance.get_hpas = AsyncMock(
        return_value=HPAListResponse(
            items=[
                HPAInfo(
                    name="backend-hpa",
                    namespace="default",
                    target="Deployment/backend",
                    min_replicas=2,
                    max_replicas=10,
                    current_replicas=2,
                    desired_replicas=4,
                    target_cpu_utilization=70,
                    current_cpu_utilization=95,
                )
            ]
        )
    )
    mock_k8s_client.return_value = mock_instance

    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as client:
        response = await client.get(
            "/api/v1/clusters/default/namespaces/default/hpas"
        )

    assert response.status_code == 200
    data = response.json()
    assert data["items"][0]["current_cpu_utilization"] == 95
    mock_instance.get_hpas.assert_called_once_with("default")


# --- Phase 5.2: error mapping reuse -----------------------------------------


@pytest.mark.asyncio
async def test_describe_pod_error_404(mock_k8s_client):
    from kubernetes.client.rest import ApiException

    mock_instance = MagicMock()
    mock_instance.describe_pod = AsyncMock(
        side_effect=ApiException(status=404, reason="Not Found")
    )
    mock_k8s_client.return_value = mock_instance

    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as client:
        response = await client.get(
            "/api/v1/clusters/default/namespaces/default/pods/nope/describe"
        )

    assert response.status_code == 404
    assert "not found" in response.json()["detail"]


@pytest.mark.asyncio
async def test_nodes_error_403(mock_k8s_client):
    from kubernetes.client.rest import ApiException

    mock_instance = MagicMock()
    mock_instance.get_nodes = AsyncMock(
        side_effect=ApiException(status=403, reason="Forbidden")
    )
    mock_k8s_client.return_value = mock_instance

    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as client:
        response = await client.get("/api/v1/clusters/default/nodes")

    assert response.status_code == 403
    assert "Access denied to nodes" in response.json()["detail"]
