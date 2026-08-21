from fastapi import APIRouter, HTTPException

from app.kubernetes.client import KubernetesClient
from app.schemas.kubernetes import (
    DaemonSetListResponse,
    DeploymentDescribe,
    DeploymentInfo,
    DeploymentListResponse,
    CronJobListResponse,
    EndpointsInfo,
    EventInfo,
    HPAListResponse,
    IngressListResponse,
    JobListResponse,
    NamespaceListResponse,
    NodeDescribe,
    NodeListResponse,
    PVCListResponse,
    PodDescribe,
    PodListResponse,
    ReplicaSetListResponse,
    ServiceInfo,
    ServiceListResponse,
    StatefulSetListResponse,
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


# --- Phase 5.2: expanded diagnostics ---------------------------------------


@router.get(
    "/clusters/{cluster}/namespaces",
    response_model=NamespaceListResponse,
)
async def get_namespaces(cluster: str) -> NamespaceListResponse:
    try:
        client = _get_client()
        return await client.get_namespaces()
    except Exception as e:
        _handle_k8s_error(e, "namespaces")


@router.get(
    "/clusters/{cluster}/nodes",
    response_model=NodeListResponse,
)
async def get_nodes(cluster: str) -> NodeListResponse:
    try:
        client = _get_client()
        return await client.get_nodes()
    except Exception as e:
        _handle_k8s_error(e, "nodes")


@router.get(
    "/clusters/{cluster}/nodes/{node_name}/describe",
    response_model=NodeDescribe,
)
async def describe_node(cluster: str, node_name: str) -> NodeDescribe:
    try:
        client = _get_client()
        return await client.describe_node(node_name)
    except Exception as e:
        _handle_k8s_error(e, "node", name=node_name)


@router.get(
    "/clusters/{cluster}/namespaces/{namespace}/pods/{pod_name}/describe",
    response_model=PodDescribe,
)
async def describe_pod(cluster: str, namespace: str, pod_name: str) -> PodDescribe:
    try:
        client = _get_client()
        return await client.describe_pod(namespace, pod_name)
    except Exception as e:
        _handle_k8s_error(e, "pod", namespace, pod_name)


@router.get(
    "/clusters/{cluster}/namespaces/{namespace}/deployments/{name}/describe",
    response_model=DeploymentDescribe,
)
async def describe_deployment(
    cluster: str, namespace: str, name: str
) -> DeploymentDescribe:
    try:
        client = _get_client()
        return await client.describe_deployment(namespace, name)
    except Exception as e:
        _handle_k8s_error(e, "deployment", namespace, name)


@router.get(
    "/clusters/{cluster}/namespaces/{namespace}/services/{name}/endpoints",
    response_model=EndpointsInfo,
)
async def get_endpoints(cluster: str, namespace: str, name: str) -> EndpointsInfo:
    try:
        client = _get_client()
        return await client.get_endpoints(namespace, name)
    except Exception as e:
        _handle_k8s_error(e, "endpoints", namespace, name)


@router.get(
    "/clusters/{cluster}/namespaces/{namespace}/pvcs",
    response_model=PVCListResponse,
)
async def get_pvcs(cluster: str, namespace: str) -> PVCListResponse:
    try:
        client = _get_client()
        return await client.get_pvcs(namespace)
    except Exception as e:
        _handle_k8s_error(e, "persistent volume claims", namespace)


@router.get(
    "/clusters/{cluster}/namespaces/{namespace}/replicasets",
    response_model=ReplicaSetListResponse,
)
async def get_replicasets(cluster: str, namespace: str) -> ReplicaSetListResponse:
    try:
        client = _get_client()
        return await client.get_replicasets(namespace)
    except Exception as e:
        _handle_k8s_error(e, "replicasets", namespace)


@router.get(
    "/clusters/{cluster}/namespaces/{namespace}/ingresses",
    response_model=IngressListResponse,
)
async def get_ingresses(cluster: str, namespace: str) -> IngressListResponse:
    try:
        client = _get_client()
        return await client.get_ingresses(namespace)
    except Exception as e:
        _handle_k8s_error(e, "ingresses", namespace)


@router.get(
    "/clusters/{cluster}/namespaces/{namespace}/statefulsets",
    response_model=StatefulSetListResponse,
)
async def get_statefulsets(cluster: str, namespace: str) -> StatefulSetListResponse:
    try:
        client = _get_client()
        return await client.get_statefulsets(namespace)
    except Exception as e:
        _handle_k8s_error(e, "statefulsets", namespace)


@router.get(
    "/clusters/{cluster}/namespaces/{namespace}/daemonsets",
    response_model=DaemonSetListResponse,
)
async def get_daemonsets(cluster: str, namespace: str) -> DaemonSetListResponse:
    try:
        client = _get_client()
        return await client.get_daemonsets(namespace)
    except Exception as e:
        _handle_k8s_error(e, "daemonsets", namespace)


@router.get(
    "/clusters/{cluster}/namespaces/{namespace}/jobs",
    response_model=JobListResponse,
)
async def get_jobs(cluster: str, namespace: str) -> JobListResponse:
    try:
        client = _get_client()
        return await client.get_jobs(namespace)
    except Exception as e:
        _handle_k8s_error(e, "jobs", namespace)


@router.get(
    "/clusters/{cluster}/namespaces/{namespace}/cronjobs",
    response_model=CronJobListResponse,
)
async def get_cronjobs(cluster: str, namespace: str) -> CronJobListResponse:
    try:
        client = _get_client()
        return await client.get_cronjobs(namespace)
    except Exception as e:
        _handle_k8s_error(e, "cronjobs", namespace)


@router.get(
    "/clusters/{cluster}/namespaces/{namespace}/hpas",
    response_model=HPAListResponse,
)
async def get_hpas(cluster: str, namespace: str) -> HPAListResponse:
    try:
        client = _get_client()
        return await client.get_hpas(namespace)
    except Exception as e:
        _handle_k8s_error(e, "horizontal pod autoscalers", namespace)


def _handle_k8s_error(
    error: Exception,
    resource_type: str,
    namespace: str | None = None,
    name: str | None = None,
) -> None:
    from kubernetes.client.rest import ApiException

    if isinstance(error, ApiException):
        if error.status == 404:
            detail = f"{resource_type.capitalize()} not found"
            if namespace:
                detail += f" in namespace '{namespace}'"
            if name:
                detail += f" (name: {name})"
            raise HTTPException(status_code=404, detail=detail)
        if error.status == 403:
            detail = f"Access denied to {resource_type}"
            if namespace:
                detail += f" in namespace '{namespace}'"
            raise HTTPException(status_code=403, detail=detail)
        if error.status == 401:
            raise HTTPException(status_code=401, detail="Kubernetes authentication failed")
        if error.status >= 500:
            raise HTTPException(status_code=503, detail="Kubernetes API unavailable")

    raise HTTPException(status_code=500, detail=f"Internal error: {error}")
