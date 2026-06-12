export type NodeType =
  | "user"
  | "service"
  | "data_store"
  | "cache"
  | "queue"
  | "external_system"
  | "worker"
  | "unknown";

export type RelationshipType =
  | "routes_to"
  | "authenticates"
  | "calls"
  | "reads_from"
  | "writes_to"
  | "stores_in"
  | "uses_storage"
  | "publishes"
  | "subscribes_to"
  | "depends_on"
  | "uses";

export type Severity = "low" | "medium" | "high" | "critical";

export type ArchitectureNode = {
  id: string;
  name: string;
  type: NodeType;
  description: string | null;
  evidence: string[];
  confidence: number | null;
  attributes: Record<string, string | number | boolean | null>;
};

export type ArchitectureEdge = {
  from: string;
  to: string;
  relationship: RelationshipType;
  description: string | null;
  evidence: string[];
  confidence: number | null;
};

export type ArchitectureGraph = {
  nodes: ArchitectureNode[];
  edges: ArchitectureEdge[];
  constraints: string[];
  unknowns: string[];
};

export type ReviewFinding = {
  id: string;
  agent_role: string;
  framework?: string | null;
  pillar?: string | null;
  risk_area?: string | null;
  severity: Severity;
  finding: string;
  evidence: string[];
  affected_components: string[];
  assumption_or_unknown?: string | null;
  recommendation: string;
  requires_adr: boolean;
};

export type ArchitectureDecision = {
  id: string;
  title: string;
  context: string;
  decision: string;
  alternatives: string[];
  consequences: string[];
  impacted_components: string[];
  linked_finding_ids: string[];
  diagram_changes: string[];
};

export type ADR = {
  id: string;
  title: string;
  status: string;
  context: string;
  decision: string;
  alternatives: string[];
  consequences: string[];
  impacted_components: string[];
  linked_findings: string[];
  diagram_changes: string[];
};

export type DiagramSpec = {
  format: string;
  content: string;
};

export type WorkflowResult = {
  architecture_v1: ArchitectureGraph;
  findings: ReviewFinding[];
  decisions: ArchitectureDecision[];
  adrs: ADR[];
  architecture_v2: ArchitectureGraph;
  diagram: DiagramSpec;
};

export type WorkflowRunResponse = {
  run_id: string;
  result: WorkflowResult;
};
