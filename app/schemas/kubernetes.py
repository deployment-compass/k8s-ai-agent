from pydantic import BaseModel


class PodInfo(BaseModel):
    name: str
    namespace: str
    status: str
    ready: bool
    restart_count: int
    node: str | None = None
    created_at: str | None = None


class PodListResponse(BaseModel):
    items: list[PodInfo]


class DeploymentInfo(BaseModel):
    name: str
    namespace: str
    replicas: int
    ready_replicas: int
    updated_replicas: int
    available_replicas: int
    conditions: list[str]


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
