from __future__ import annotations

from kubernetes import client

from app.schemas.kubernetes import (
    DeploymentInfo,
    DeploymentListResponse,
    EventInfo,
    PodInfo,
    PodListResponse,
    ServiceInfo,
    ServiceListResponse,
)


class KubernetesClient:

    def __init__(self) -> None:
        self._core = client.CoreV1Api()
        self._apps = client.AppsV1Api()

    async def get_pods(self, namespace: str) -> PodListResponse:
        pods = self._core.list_namespaced_pod(namespace=namespace)
        items = [
            PodInfo(
                name=pod.metadata.name,
                namespace=pod.metadata.namespace,
                status=pod.status.phase,
                ready=self._is_pod_ready(pod),
                restart_count=self._get_restart_count(pod),
                node=pod.spec.node_name,
                created_at=str(pod.metadata.creation_timestamp),
            )
            for pod in pods.items
        ]
        return PodListResponse(items=items)

    async def get_deployments(self, namespace: str) -> DeploymentListResponse:
        deps = self._apps.list_namespaced_deployment(namespace=namespace)
        items = [
            DeploymentInfo(
                name=dep.metadata.name,
                namespace=dep.metadata.namespace,
                replicas=dep.spec.replicas or 0,
                ready_replicas=dep.status.ready_replicas or 0,
                updated_replicas=dep.status.updated_replicas or 0,
                available_replicas=dep.status.available_replicas or 0,
                conditions=[
                    f"{c.type}={c.status}"
                    for c in (dep.status.conditions or [])
                ],
            )
            for dep in deps.items
        ]
        return DeploymentListResponse(items=items)

    async def get_deployment(self, namespace: str, name: str) -> DeploymentInfo:
        dep = self._apps.read_namespaced_deployment(name=name, namespace=namespace)
        conditions = []
        if dep.status.conditions:
            conditions = [
                f"{c.type}={c.status}" for c in dep.status.conditions
            ]
        return DeploymentInfo(
            name=dep.metadata.name,
            namespace=dep.metadata.namespace,
            replicas=dep.spec.replicas or 0,
            ready_replicas=dep.status.ready_replicas or 0,
            updated_replicas=dep.status.updated_replicas or 0,
            available_replicas=dep.status.available_replicas or 0,
            conditions=conditions,
        )

    async def get_service(self, namespace: str, name: str) -> ServiceInfo:
        svc = self._core.read_namespaced_service(name=name, namespace=namespace)
        ports = [
            f"{p.port}/{p.protocol} -> {p.target_port}"
            for p in (svc.spec.ports or [])
        ]
        return ServiceInfo(
            name=svc.metadata.name,
            namespace=svc.metadata.namespace,
            type=svc.spec.type,
            cluster_ip=svc.spec.cluster_ip,
            ports=ports,
        )

    async def get_services(self, namespace: str) -> ServiceListResponse:
        svcs = self._core.list_namespaced_service(namespace=namespace)
        items = [
            ServiceInfo(
                name=svc.metadata.name,
                namespace=svc.metadata.namespace,
                type=svc.spec.type,
                cluster_ip=svc.spec.cluster_ip,
                ports=[
                    f"{p.port}/{p.protocol} -> {p.target_port}"
                    for p in (svc.spec.ports or [])
                ],
            )
            for svc in svcs.items
        ]
        return ServiceListResponse(items=items)

    async def get_pod_logs(self, namespace: str, pod_name: str) -> str:
        logs = self._core.read_namespaced_pod_log(
            name=pod_name, namespace=namespace
        )
        if isinstance(logs, bytes):
            return logs.decode("utf-8", errors="replace")
        return logs

    async def get_events(self, namespace: str) -> list[EventInfo]:
        events = self._core.list_namespaced_event(namespace=namespace)
        items = [
            EventInfo(
                name=event.metadata.name,
                namespace=event.metadata.namespace,
                type=event.type or "Normal",
                reason=event.reason or "",
                message=event.message or "",
                count=event.count or 0,
                first_seen=str(event.first_timestamp) if event.first_timestamp else None,
                last_seen=str(event.last_timestamp) if event.last_timestamp else None,
                involved_object=f"{event.involved_object.kind}/{event.involved_object.name}"
                if event.involved_object
                else "",
            )
            for event in events.items
        ]
        return items

    @staticmethod
    def _is_pod_ready(pod) -> bool:
        if not pod.status.conditions:
            return False
        return any(
            c.type == "Ready" and c.status == "True"
            for c in pod.status.conditions
        )

    @staticmethod
    def _get_restart_count(pod) -> int:
        if not pod.status.container_statuses:
            return 0
        return sum(cs.restart_count for cs in pod.status.container_statuses)
