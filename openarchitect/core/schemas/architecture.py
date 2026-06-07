from enum import StrEnum

from pydantic import BaseModel, Field, field_validator


AttributeValue = str | int | float | bool | None


class NodeType(StrEnum):
    USER = "user"
    SERVICE = "service"
    DATA_STORE = "data_store"
    CACHE = "cache"
    QUEUE = "queue"
    EXTERNAL_SYSTEM = "external_system"
    WORKER = "worker"
    UNKNOWN = "unknown"


class RelationshipType(StrEnum):
    ROUTES_TO = "routes_to"
    AUTHENTICATES = "authenticates"
    CALLS = "calls"
    READS_FROM = "reads_from"
    WRITES_TO = "writes_to"
    STORES_IN = "stores_in"
    USES_STORAGE = "uses_storage"
    PUBLISHES = "publishes"
    SUBSCRIBES_TO = "subscribes_to"
    DEPENDS_ON = "depends_on"
    USES = "uses"


class ArchitectureNode(BaseModel):
    id: str
    name: str
    type: NodeType = NodeType.UNKNOWN
    description: str | None = None
    evidence: list[str] = Field(default_factory=list)
    confidence: float | None = Field(default=None, ge=0, le=1)
    attributes: dict[str, AttributeValue] = Field(default_factory=dict)

    @field_validator("type", mode="before")
    @classmethod
    def unknown_type_when_invalid(cls, value):
        if value in {item.value for item in NodeType}:
            return value
        return NodeType.UNKNOWN

    @field_validator("evidence", mode="before")
    @classmethod
    def empty_evidence_when_null(cls, value):
        return [] if value is None else value

    @field_validator("attributes", mode="before")
    @classmethod
    def empty_attributes_when_null(cls, value):
        return {} if value is None else value


class ArchitectureEdge(BaseModel):
    from_node: str = Field(alias="from")
    to_node: str = Field(alias="to")
    relationship: RelationshipType
    description: str | None = None
    evidence: list[str] = Field(default_factory=list)
    confidence: float | None = Field(default=None, ge=0, le=1)

    @field_validator("relationship", mode="before")
    @classmethod
    def depends_on_when_relationship_invalid(cls, value):
        if value in {item.value for item in RelationshipType}:
            return value
        return RelationshipType.DEPENDS_ON

    @field_validator("evidence", mode="before")
    @classmethod
    def empty_evidence_when_null(cls, value):
        return [] if value is None else value


class ArchitectureGraph(BaseModel):
    nodes: list[ArchitectureNode] = Field(default_factory=list)
    edges: list[ArchitectureEdge] = Field(default_factory=list)
    constraints: list[str] = Field(default_factory=list)
    unknowns: list[str] = Field(default_factory=list)

    @field_validator("nodes", "edges", "constraints", "unknowns", mode="before")
    @classmethod
    def empty_collection_when_null(cls, value):
        return [] if value is None else value

    @field_validator("constraints", "unknowns", mode="before")
    @classmethod
    def stringify_text_collections(cls, value):
        if value is None:
            return []
        return [_stringify_text_item(item) for item in value]


def _stringify_text_item(item) -> str:
    if isinstance(item, str):
        return item
    if isinstance(item, dict):
        for key in ("description", "text", "value", "name"):
            if key in item and item[key] is not None:
                return str(item[key])
    return str(item)
