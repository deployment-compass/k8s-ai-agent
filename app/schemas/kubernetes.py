from pydantic import BaseModel


class ContainerInfo(BaseModel):
    name: str
    image: str | None = None
    state: str
    ready: bool | None = None
    restart_count: int = 0
    waiting_reason: str | None = None
    last_termination_reason: str | None = None
    exit_code: int | None = None


class PodInfo(BaseModel):
    name: str
    namespace: str
    status: str
    ready: bool
    restart_count: int
    node: str | None = None
    created_at: str | None = None
    containers: list[ContainerInfo] = []


class PodListResponse(BaseModel):
    items: list[PodInfo]


class ContainerDetail(ContainerInfo):
    started_at: str | None = None
    finished_at: str | None = None
    probes: list[str] = []
    resources: dict[str, dict[str, str]] = {}


class VolumeSummary(BaseModel):
    name: str
    type: str
    claim_name: str | None = None


class PodDescribe(BaseModel):
    name: str
    namespace: str
    phase: str
    node: str | None = None
    created_at: str | None = None
    conditions: list[str]
    init_containers: list[ContainerDetail]
    containers: list[ContainerDetail]
    volumes: list[VolumeSummary]
    owner_chain: list[str]
    node_selector: dict[str, str] | None = None


class DeploymentCondition(BaseModel):
    type: str
    status: str
    reason: str | None = None
    message: str | None = None
    last_update: str | None = None


class ReplicaSetSummary(BaseModel):
    name: str
    desired: int
    ready: int
    revision: str | None = None


class DeploymentInfo(BaseModel):
    name: str
    namespace: str
    replicas: int
    ready_replicas: int
    updated_replicas: int
    available_replicas: int
    conditions: list[str]


class DeploymentDescribe(BaseModel):
    name: str
    namespace: str
    replicas: int
    ready_replicas: int
    updated_replicas: int
    available_replicas: int
    strategy: str
    max_surge: str | None = None
    max_unavailable: str | None = None
    selector: dict[str, str]
    conditions: list[DeploymentCondition]
    images: list[str]
    owned_replicasets: list[ReplicaSetSummary]


class DeploymentListResponse(BaseModel):
    items: list[DeploymentInfo]


class ServiceInfo(BaseModel):
    name: str
    namespace: str
    type: str
    cluster_ip: str | None = None
    ports: list[str]


class ServiceListResponse(BaseModel):
    items: list[ServiceInfo]


class EventInfo(BaseModel):
    name: str
    namespace: str
    type: str
    reason: str
    message: str
    count: int
    first_seen: str | None = None
    last_seen: str | None = None
    involved_object: str


class NamespaceInfo(BaseModel):
    name: str
    phase: str
    created_at: str | None = None


class NamespaceListResponse(BaseModel):
    items: list[NamespaceInfo]


class EndpointPortInfo(BaseModel):
    port: int
    protocol: str | None = None
    name: str | None = None


class EndpointsInfo(BaseModel):
    name: str
    namespace: str
    addresses: list[str]
    not_ready_addresses: list[str]
    ports: list[EndpointPortInfo]


class PVCInfo(BaseModel):
    name: str
    namespace: str
    phase: str
    capacity: str | None = None
    storage_class: str | None = None


class PVCListResponse(BaseModel):
    items: list[PVCInfo]


class NodeInfo(BaseModel):
    name: str
    ready: bool
    kubelet_version: str | None = None


class NodeListResponse(BaseModel):
    items: list[NodeInfo]


class NodeConditionInfo(BaseModel):
    type: str
    status: str
    reason: str | None = None
    message: str | None = None


class NodeTaintInfo(BaseModel):
    key: str
    effect: str | None = None
    value: str | None = None


class NodeDescribe(BaseModel):
    name: str
    ready: bool
    unschedulable: bool
    kubelet_version: str | None = None
    conditions: list[NodeConditionInfo]
    taints: list[NodeTaintInfo]
    allocatable: dict[str, str]
    capacity: dict[str, str]
    addresses: list[str]


class ReplicaSetInfo(BaseModel):
    name: str
    namespace: str
    desired: int
    ready: int
    revision: str | None = None
    owner_deployment: str | None = None


class ReplicaSetListResponse(BaseModel):
    items: list[ReplicaSetInfo]


class IngressRulePath(BaseModel):
    path: str
    service_name: str | None = None
    service_port: int | str | None = None


class IngressRuleInfo(BaseModel):
    host: str
    paths: list[IngressRulePath]


class IngressInfo(BaseModel):
    name: str
    namespace: str
    rules: list[IngressRuleInfo]
    tls_hosts: list[str]


class IngressListResponse(BaseModel):
    items: list[IngressInfo]


class StatefulSetInfo(BaseModel):
    name: str
    namespace: str
    replicas: int
    ready_replicas: int
    updated_replicas: int
    conditions: list[str]


class StatefulSetListResponse(BaseModel):
    items: list[StatefulSetInfo]


class DaemonSetInfo(BaseModel):
    name: str
    namespace: str
    desired_scheduled: int
    ready: int
    available: int
    updated: int


class DaemonSetListResponse(BaseModel):
    items: list[DaemonSetInfo]


class JobInfo(BaseModel):
    name: str
    namespace: str
    active: int
    succeeded: int
    failed: int
    completions: int | None = None
    start_time: str | None = None


class JobListResponse(BaseModel):
    items: list[JobInfo]


class CronJobInfo(BaseModel):
    name: str
    namespace: str
    schedule: str
    suspend: bool
    active_jobs: int
    last_schedule_time: str | None = None


class CronJobListResponse(BaseModel):
    items: list[CronJobInfo]


class HPAInfo(BaseModel):
    name: str
    namespace: str
    target: str
    min_replicas: int | None = None
    max_replicas: int
    current_replicas: int
    desired_replicas: int
    target_cpu_utilization: int | None = None
    current_cpu_utilization: int | None = None


class HPAListResponse(BaseModel):
    items: list[HPAInfo]
