from fastapi import APIRouter, HTTPException

from app.kubernetes.client import KubernetesClient
from app.schemas.kubernetes import (
    DeploymentInfo,
    DeploymentListResponse,
    EventInfo,
    PodListResponse,
    ServiceInfo,
    ServiceListResponse,
)

router = APIRouter(tags=["kubernetes"])


def _get_client() -> KubernetesClient:
    return KubernetesClient()


@router.get(
    "/clusters/{cluster}/namespaces/{namespace}/pods",
    response_model=PodListResponse,
)
async def get_pods(cluster: str, namespace: str) -> PodListResponse:
    try:
        client = _get_client()
        return await client.get_pods(namespace)
    except Exception as e:
        _handle_k8s_error(e, "pods", namespace)


@router.get(
    "/clusters/{cluster}/namespaces/{namespace}/deployments",
    response_model=DeploymentListResponse,
)
async def get_deployments(cluster: str, namespace: str) -> DeploymentListResponse:
    try:
        client = _get_client()
        return await client.get_deployments(namespace)
    except Exception as e:
        _handle_k8s_error(e, "deployments", namespace)


@router.get(
    "/clusters/{cluster}/namespaces/{namespace}/deployments/{name}",
    response_model=DeploymentInfo,
)
async def get_deployment(cluster: str, namespace: str, name: str) -> DeploymentInfo:
    try:
        client = _get_client()
        return await client.get_deployment(namespace, name)
    except Exception as e:
        _handle_k8s_error(e, "deployment", namespace, name)


@router.get(
    "/clusters/{cluster}/namespaces/{namespace}/services/{name}",
    response_model=ServiceInfo,
)
async def get_service(cluster: str, namespace: str, name: str) -> ServiceInfo:
    try:
        client = _get_client()
        return await client.get_service(namespace, name)
    except Exception as e:
        _handle_k8s_error(e, "service", namespace, name)


@router.get(
    "/clusters/{cluster}/namespaces/{namespace}/services",
    response_model=ServiceListResponse,
)
async def get_services(cluster: str, namespace: str) -> ServiceListResponse:
    try:
        client = _get_client()
        return await client.get_services(namespace)
    except Exception as e:
        _handle_k8s_error(e, "services", namespace)


@router.get(
    "/clusters/{cluster}/namespaces/{namespace}/pods/{pod_name}/logs",
)
async def get_pod_logs(cluster: str, namespace: str, pod_name: str) -> str:
    try:
        client = _get_client()
        return await client.get_pod_logs(namespace, pod_name)
    except Exception as e:
        _handle_k8s_error(e, "pod logs", namespace, pod_name)


@router.get(
    "/clusters/{cluster}/namespaces/{namespace}/events",
    response_model=list[EventInfo],
)
async def get_events(cluster: str, namespace: str) -> list[EventInfo]:
    try:
        client = _get_client()
        return await client.get_events(namespace)
    except Exception as e:
        _handle_k8s_error(e, "events", namespace)


def _handle_k8s_error(
    error: Exception,
    resource_type: str,
    namespace: str,
    name: str | None = None,
) -> None:
    from kubernetes.client.rest import ApiException

    if isinstance(error, ApiException):
        if error.status == 404:
            detail = f"{resource_type.capitalize()} not found in namespace '{namespace}'"
            if name:
                detail += f" (name: {name})"
            raise HTTPException(status_code=404, detail=detail)
        if error.status == 403:
            raise HTTPException(
                status_code=403,
                detail=f"Access denied to {resource_type} in namespace '{namespace}'",
            )
        if error.status == 401:
            raise HTTPException(status_code=401, detail="Kubernetes authentication failed")
        if error.status >= 500:
            raise HTTPException(status_code=503, detail="Kubernetes API unavailable")

    raise HTTPException(status_code=500, detail=f"Internal error: {error}")
