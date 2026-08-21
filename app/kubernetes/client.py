from __future__ import annotations

from kubernetes import client
from kubernetes.client import ApiException

from app.schemas.kubernetes import (
    ContainerDetail,
    ContainerInfo,
    CronJobInfo,
    CronJobListResponse,
    DaemonSetInfo,
    DaemonSetListResponse,
    DeploymentCondition,
    DeploymentDescribe,
    DeploymentInfo,
    DeploymentListResponse,
    EndpointsInfo,
    EndpointPortInfo,
    EventInfo,
    HPAInfo,
    HPAListResponse,
    IngressInfo,
    IngressListResponse,
    IngressRuleInfo,
    IngressRulePath,
    JobInfo,
    JobListResponse,
    NamespaceInfo,
    NamespaceListResponse,
    NodeConditionInfo,
    NodeDescribe,
    NodeInfo,
    NodeListResponse,
    NodeTaintInfo,
    PVCInfo,
    PVCListResponse,
    PodDescribe,
    PodInfo,
    PodListResponse,
    ReplicaSetInfo,
    ReplicaSetListResponse,
    ReplicaSetSummary,
    ServiceInfo,
    ServiceListResponse,
    StatefulSetInfo,
    StatefulSetListResponse,
    VolumeSummary,
)

_ALLOCATABLE_KEYS = ("cpu", "memory", "pods")
_VOLUME_TYPE_FIELDS = (
    "host_path",
    "persistent_volume_claim",
    "empty_dir",
    "config_map",
    "secret",
    "projected",
    "downward_api",
    "nfs",
    "csi",
)


class KubernetesClient:

    def __init__(self) -> None:
        self._core = client.CoreV1Api()
        self._apps = client.AppsV1Api()
        self._batch = client.BatchV1Api()
        self._networking = client.NetworkingV1Api()
        self._autoscaling = client.AutoscalingV2Api()

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
                containers=self._container_infos(pod),
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

    async def get_namespaces(self) -> NamespaceListResponse:
        namespaces = self._core.list_namespace()
        items = [
            NamespaceInfo(
                name=ns.metadata.name,
                phase=ns.status.phase if ns.status else "Unknown",
                created_at=str(ns.metadata.creation_timestamp),
            )
            for ns in namespaces.items
        ]
        return NamespaceListResponse(items=items)

    async def describe_pod(self, namespace: str, pod_name: str) -> PodDescribe:
        pod = self._core.read_namespaced_pod(name=pod_name, namespace=namespace)
        return PodDescribe(
            name=pod.metadata.name,
            namespace=pod.metadata.namespace,
            phase=pod.status.phase if pod.status else "Unknown",
            node=pod.spec.node_name,
            created_at=str(pod.metadata.creation_timestamp),
            conditions=[
                f"{c.type}={c.status}"
                + (f" ({c.reason})" if c.reason else "")
                for c in (pod.status.conditions or [])
            ],
            init_containers=self._container_details(pod, init=True),
            containers=self._container_details(pod),
            volumes=self._volume_summaries(pod),
            owner_chain=await self._owner_chain(namespace, pod.metadata.owner_references),
            node_selector=dict(pod.spec.node_selector or {}) or None,
        )

    async def describe_deployment(
        self, namespace: str, name: str
    ) -> DeploymentDescribe:
        dep = self._apps.read_namespaced_deployment(name=name, namespace=namespace)
        strategy = dep.spec.strategy or None
        rolling = strategy.rolling_update if strategy else None
        selector = dict(dep.spec.selector.match_labels or {})
        return DeploymentDescribe(
            name=dep.metadata.name,
            namespace=dep.metadata.namespace,
            replicas=dep.spec.replicas or 0,
            ready_replicas=dep.status.ready_replicas or 0,
            updated_replicas=dep.status.updated_replicas or 0,
            available_replicas=dep.status.available_replicas or 0,
            strategy=strategy.type if strategy else "Unknown",
            max_surge=str(rolling.max_surge) if rolling and rolling.max_surge is not None else None,
            max_unavailable=(
                str(rolling.max_unavailable)
                if rolling and rolling.max_unavailable is not None
                else None
            ),
            selector=selector,
            conditions=[
                DeploymentCondition(
                    type=c.type,
                    status=c.status,
                    reason=c.reason,
                    message=c.message,
                    last_update=str(c.last_update_time) if c.last_update_time else None,
                )
                for c in (dep.status.conditions or [])
            ],
            images=[c.image for c in (dep.spec.template.spec.containers or [])],
            owned_replicasets=await self._owned_replicasets(
                namespace, dep.metadata.name, dep.spec.selector.match_labels or {}
            ),
        )

    async def get_endpoints(self, namespace: str, service_name: str) -> EndpointsInfo:
        eps = self._core.read_namespaced_endpoints(
            name=service_name, namespace=namespace
        )
        addresses: list[str] = []
        not_ready_addresses: list[str] = []
        ports: list = []
        for subset in eps.subsets or []:
            addresses.extend(
                a.ip for a in (subset.addresses or [])
            )
            not_ready_addresses.extend(
                a.ip for a in (subset.not_ready_addresses or [])
            )
            ports.extend(
                EndpointPortInfo(
                    port=p.port,
                    protocol=p.protocol,
                    name=p.name,
                )
                for p in (subset.ports or [])
            )
        return EndpointsInfo(
            name=eps.metadata.name,
            namespace=eps.metadata.namespace,
            addresses=addresses,
            not_ready_addresses=not_ready_addresses,
            ports=ports,
        )

    async def get_pvcs(self, namespace: str) -> PVCListResponse:
        pvcs = self._core.list_namespaced_persistent_volume_claim(
            namespace=namespace
        )
        items = [
            PVCInfo(
                name=pvc.metadata.name,
                namespace=pvc.metadata.namespace,
                phase=pvc.status.phase if pvc.status else "Unknown",
                capacity=(pvc.status.capacity or {}).get("storage") if pvc.status else None,
                storage_class=pvc.spec.storage_class_name,
            )
            for pvc in pvcs.items
        ]
        return PVCListResponse(items=items)

    async def get_nodes(self) -> NodeListResponse:
        nodes = self._core.list_node()
        items = [
            NodeInfo(
                name=node.metadata.name,
                ready=self._node_ready(node),
                kubelet_version=(
                    node.status.node_info.kubelet_version if node.status.node_info else None
                ),
            )
            for node in nodes.items
        ]
        return NodeListResponse(items=items)

    async def describe_node(self, node_name: str) -> NodeDescribe:
        node = self._core.read_node(name=node_name)
        status = node.status or client.V1NodeStatus()
        return NodeDescribe(
            name=node.metadata.name,
            ready=self._node_ready(node),
            unschedulable=bool(node.spec.unschedulable),
            kubelet_version=(
                status.node_info.kubelet_version if status.node_info else None
            ),
            conditions=[
                NodeConditionInfo(
                    type=c.type,
                    status=c.status,
                    reason=c.reason,
                    message=c.message,
                )
                for c in (status.conditions or [])
            ],
            taints=[
                NodeTaintInfo(key=t.key, effect=t.effect, value=t.value)
                for t in (node.spec.taints or [])
            ],
            allocatable={
                k: str(v)
                for k, v in (status.allocatable or {}).items()
                if k in _ALLOCATABLE_KEYS
            },
            capacity={
                k: str(v)
                for k, v in (status.capacity or {}).items()
                if k in _ALLOCATABLE_KEYS
            },
            addresses=[
                f"{a.type}={a.address}" for a in (status.addresses or [])
            ],
        )

    async def get_replicasets(self, namespace: str) -> ReplicaSetListResponse:
        rses = self._apps.list_namespaced_replica_set(namespace=namespace)
        items = [
            ReplicaSetInfo(
                name=rs.metadata.name,
                namespace=rs.metadata.namespace,
                desired=rs.spec.replicas or 0,
                ready=rs.status.ready_replicas or 0,
                revision=(
                    (rs.metadata.annotations or {}).get(
                        "deployment.kubernetes.io/revision"
                    )
                ),
                owner_deployment=self._owner_name(rs.metadata.owner_references, "Deployment"),
            )
            for rs in rses.items
        ]
        return ReplicaSetListResponse(items=items)

    async def get_ingresses(self, namespace: str) -> IngressListResponse:
        ingresses = self._networking.list_namespaced_ingress(namespace=namespace)
        items = [
            IngressInfo(
                name=ing.metadata.name,
                namespace=ing.metadata.namespace,
                rules=[
                    IngressRuleInfo(
                        host=rule.host or "*",
                        paths=[
                            IngressRulePath(
                                path=p.path or "/",
                                service_name=(
                                    p.backend.service.name
                                    if p.backend and p.backend.service
                                    else None
                                ),
                                service_port=(
                                    (
                                        p.backend.service.port.number
                                        if p.backend.service.port.number is not None
                                        else p.backend.service.port.name
                                    )
                                    if p.backend and p.backend.service and p.backend.service.port
                                    else None
                                ),
                            )
                            for p in (rule.http.paths if rule.http else [])
                        ],
                    )
                    for rule in (ing.spec.rules or [])
                ]
                if ing.spec
                else [],
                tls_hosts=[
                    host
                    for tls in ((ing.spec.tls if ing.spec else None) or [])
                    for host in (tls.hosts or [])
                ],
            )
            for ing in ingresses.items
        ]
        return IngressListResponse(items=items)

    async def get_statefulsets(self, namespace: str) -> StatefulSetListResponse:
        sts = self._apps.list_namespaced_stateful_set(namespace=namespace)
        items = [
            StatefulSetInfo(
                name=s.metadata.name,
                namespace=s.metadata.namespace,
                replicas=s.spec.replicas or 0,
                ready_replicas=s.status.ready_replicas or 0,
                updated_replicas=s.status.updated_replicas or 0,
                conditions=[
                    f"{c.type}={c.status}" for c in (s.status.conditions or [])
                ],
            )
            for s in sts.items
        ]
        return StatefulSetListResponse(items=items)

    async def get_daemonsets(self, namespace: str) -> DaemonSetListResponse:
        ds = self._apps.list_namespaced_daemon_set(namespace=namespace)
        items = [
            DaemonSetInfo(
                name=d.metadata.name,
                namespace=d.metadata.namespace,
                desired_scheduled=d.status.desired_number_scheduled or 0,
                ready=d.status.number_ready or 0,
                available=d.status.number_available or 0,
                updated=d.status.updated_number_scheduled or 0,
            )
            for d in ds.items
        ]
        return DaemonSetListResponse(items=items)

    async def get_jobs(self, namespace: str) -> JobListResponse:
        jobs = self._batch.list_namespaced_job(namespace=namespace)
        items = [
            JobInfo(
                name=j.metadata.name,
                namespace=j.metadata.namespace,
                active=j.status.active or 0,
                succeeded=j.status.succeeded or 0,
                failed=j.status.failed or 0,
                completions=j.spec.completions,
                start_time=str(j.status.start_time) if j.status.start_time else None,
            )
            for j in jobs.items
        ]
        return JobListResponse(items=items)

    async def get_cronjobs(self, namespace: str) -> CronJobListResponse:
        cronjobs = self._batch.list_namespaced_cron_job(namespace=namespace)
        items = [
            CronJobInfo(
                name=cj.metadata.name,
                namespace=cj.metadata.namespace,
                schedule=cj.spec.schedule,
                suspend=bool(cj.spec.suspend),
                active_jobs=len(cj.status.active or []),
                last_schedule_time=(
                    str(cj.status.last_schedule_time)
                    if cj.status.last_schedule_time
                    else None
                ),
            )
            for cj in cronjobs.items
        ]
        return CronJobListResponse(items=items)

    async def get_hpas(self, namespace: str) -> HPAListResponse:
        hpas = self._autoscaling.list_namespaced_horizontal_pod_autoscaler(
            namespace=namespace
        )
        items = [self._hpa_info(hpa) for hpa in hpas.items]
        return HPAListResponse(items=items)

    @staticmethod
    def _cpu_utilization(metrics) -> int | None:
        for m in metrics or []:
            if m.type == "Resource" and m.resource and m.resource.name == "cpu":
                return m.resource.current.average_utilization
        return None

    @classmethod
    def _hpa_info(cls, hpa) -> HPAInfo:
        target_cpu = None
        for m in (hpa.spec.metrics or []):
            if m.type == "Resource" and m.resource and m.resource.name == "cpu":
                target_cpu = m.resource.target.average_utilization
        ref = hpa.spec.scale_target_ref
        return HPAInfo(
            name=hpa.metadata.name,
            namespace=hpa.metadata.namespace,
            target=f"{ref.kind}/{ref.name}",
            min_replicas=hpa.spec.min_replicas,
            max_replicas=hpa.spec.max_replicas,
            current_replicas=hpa.status.current_replicas or 0,
            desired_replicas=hpa.status.desired_replicas or 0,
            target_cpu_utilization=target_cpu,
            current_cpu_utilization=cls._cpu_utilization(hpa.status.current_metrics),
        )

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

    @staticmethod
    def _node_ready(node) -> bool:
        if not node.status or not node.status.conditions:
            return False
        return any(
            c.type == "Ready" and c.status == "True"
            for c in node.status.conditions
        )

    @staticmethod
    def _container_state_fields(container_status) -> dict:
        state = "unknown"
        waiting_reason = None
        exit_code = None
        last_termination_reason = None

        cs = container_status.state
        if cs is not None:
            if cs.waiting is not None:
                state = "waiting"
                waiting_reason = cs.waiting.reason or None
            elif cs.running is not None:
                state = "running"
            elif cs.terminated is not None:
                state = "terminated"
                last_termination_reason = cs.terminated.reason or None
                exit_code = cs.terminated.exit_code

        if container_status.last_state is not None and (
            container_status.last_state.terminated is not None
        ):
            terminated = container_status.last_state.terminated
            last_termination_reason = (
                last_termination_reason or terminated.reason or None
            )
            if exit_code is None:
                exit_code = terminated.exit_code

        return {
            "state": state,
            "waiting_reason": waiting_reason,
            "last_termination_reason": last_termination_reason,
            "exit_code": exit_code,
        }

    @classmethod
    def _container_infos(cls, pod) -> list[ContainerInfo]:
        spec_containers = pod.spec.containers or []
        statuses = {
            cs.name: cs for cs in (pod.status.container_statuses or [])
        }
        items = []
        for sc in spec_containers:
            status = statuses.get(sc.name)
            fields = (
                cls._container_state_fields(status)
                if status is not None
                else {"state": "unknown", "waiting_reason": None,
                      "last_termination_reason": None, "exit_code": None}
            )
            items.append(
                ContainerInfo(
                    name=sc.name,
                    image=sc.image,
                    ready=status.ready if status else None,
                    restart_count=status.restart_count if status else 0,
                    **fields,
                )
            )
        return items

    @classmethod
    def _container_details(cls, pod, init: bool = False) -> list[ContainerDetail]:
        spec_containers = (
            pod.spec.init_containers or [] if init else pod.spec.containers or []
        )
        statuses = {
            cs.name: cs for cs in (pod.status.init_container_statuses or [])
        } if init else {cs.name: cs for cs in (pod.status.container_statuses or [])}
        items = []
        for sc in spec_containers:
            status = statuses.get(sc.name)
            fields = (
                cls._container_state_fields(status)
                if status is not None
                else {"state": "unknown", "waiting_reason": None,
                      "last_termination_reason": None, "exit_code": None}
            )
            started_at = finished_at = None
            if status is not None and status.state is not None:
                if status.state.running is not None:
                    started_at = (
                        str(status.state.running.started_at)
                        if status.state.running.started_at
                        else None
                    )
                if status.state.terminated is not None:
                    started_at = started_at or (
                        str(status.state.terminated.started_at)
                        if status.state.terminated.started_at
                        else None
                    )
                    finished_at = (
                        str(status.state.terminated.finished_at)
                        if status.state.terminated.finished_at
                        else None
                    )
            items.append(
                ContainerDetail(
                    name=sc.name,
                    image=sc.image,
                    ready=status.ready if status else None,
                    restart_count=status.restart_count if status else 0,
                    started_at=started_at,
                    finished_at=finished_at,
                    probes=cls._probe_summaries(sc),
                    resources=cls._resource_summary(sc),
                    **fields,
                )
            )
        return items

    @staticmethod
    def _probe_summaries(spec_container) -> list[str]:
        probes = []
        for probe_type in ("liveness_probe", "readiness_probe", "startup_probe"):
            probe = getattr(spec_container, probe_type, None)
            if probe is None:
                continue
            label = probe_type.removesuffix("_probe").capitalize()
            detail = "?"
            if probe.http_get is not None:
                path = probe.http_get.path or "/"
                detail = f"HTTP GET {path}:{probe.http_get.port}"
            elif probe.tcp_socket is not None:
                detail = f"TCP :{probe.tcp_socket.port}"
            elif probe.exec is not None and probe.exec.command:
                detail = f"EXEC {probe.exec.command[0]}"
            elif probe.grpc is not None:
                detail = f"GRPC :{probe.grpc.port}"
            probes.append(
                f"{label}={detail} delay={probe.initial_delay_seconds}s period={probe.period_seconds}s"
            )
        return probes

    @staticmethod
    def _resource_summary(spec_container) -> dict[str, dict[str, str]]:
        requirements = spec_container.resources
        if requirements is None:
            return {}
        summary: dict[str, dict[str, str]] = {}
        for key, attr in (("requests", "requests"), ("limits", "limits")):
            values = getattr(requirements, attr, None) or {}
            if values:
                summary[key] = {name: str(amount) for name, amount in values.items()}
        return summary

    @classmethod
    def _volume_summaries(cls, pod) -> list[VolumeSummary]:
        items = []
        for volume in (pod.spec.volumes or []):
            vtype = next(
                (
                    field
                    for field in _VOLUME_TYPE_FIELDS
                    if getattr(volume, field, None) is not None
                ),
                "other",
            )
            claim_name = None
            if vtype == "persistentVolumeClaim":
                pvc_source = volume.persistent_volume_claim
                # PVC names are fine to expose; ConfigMap/Secret references are not.
                claim_name = (
                    pvc_source.claim_name if pvc_source is not None else None
                )
            items.append(VolumeSummary(name=volume.name, type=vtype, claim_name=claim_name))
        return items

    async def _owner_chain(self, namespace: str, owner_references) -> list[str]:
        chain: list[str] = []
        ref = next(
            (o for o in (owner_references or []) if o.kind), None
        )
        while ref is not None:
            chain.append(f"{ref.kind}/{ref.name}")
            if ref.kind != "ReplicaSet":
                break
            try:
                rs = self._apps.read_namespaced_replica_set(
                    name=ref.name, namespace=namespace
                )
            except ApiException:
                break
            ref = next((o for o in (rs.metadata.owner_references or []) if o.kind), None)
        return chain

    @staticmethod
    def _owner_name(owner_references, kind: str) -> str | None:
        for ref in owner_references or []:
            if ref.kind == kind:
                return ref.name
        return None

    async def _owned_replicasets(
        self, namespace: str, deployment_name: str, selector: dict
    ) -> list[ReplicaSetSummary]:
        label_selector = ",".join(f"{k}={v}" for k, v in selector.items())
        rses = self._apps.list_namespaced_replica_set(
            namespace=namespace, label_selector=label_selector
        )
        owned = [
            rs for rs in rses.items
            if self._owner_name(rs.metadata.owner_references, "Deployment") == deployment_name
        ]
        owned.sort(key=lambda rs: str(rs.metadata.creation_timestamp or ""), reverse=True)
        return [
            ReplicaSetSummary(
                name=rs.metadata.name,
                desired=rs.spec.replicas or 0,
                ready=rs.status.ready_replicas or 0,
                revision=(rs.metadata.annotations or {}).get(
                    "deployment.kubernetes.io/revision"
                ),
            )
            for rs in owned
        ]
