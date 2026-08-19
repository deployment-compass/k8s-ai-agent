from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from httpx import ASGITransport, AsyncClient

from app.main import app
from app.schemas.kubernetes import (
    DeploymentInfo,
    DeploymentListResponse,
    EventInfo,
    PodInfo,
    PodListResponse,
    ServiceInfo,
    ServiceListResponse,
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
