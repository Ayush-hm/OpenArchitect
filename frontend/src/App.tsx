import { ChangeEvent, ReactNode, useEffect, useMemo, useState } from "react";
import {
  AlertTriangle,
  Braces,
  CheckCircle2,
  CircleDot,
  FileText,
  GitCompare,
  Loader2,
  Network,
  Play,
  ScrollText,
  Upload,
} from "lucide-react";
import { fetchHealth, uploadArchitectureDocument } from "./api";
import { buildGraphDiff, graphToMermaid } from "./graph";
import { MermaidDiagram } from "./components/MermaidDiagram";
import type { ADR, ReviewFinding, WorkflowRunResponse } from "./types";

type View = "overview" | "architecture" | "findings" | "adrs" | "changes" | "json";
type GraphView = "current" | "target";
type Summary = {
  components: number;
  critical: number;
  high: number;
  adrs: number;
  changes: number;
};

const workflowStages = [
  "Ingestion",
  "Architecture Extraction",
  "Graph Critic",
  "Specialist Review",
  "Finding Coverage",
  "Lead Architect",
  "ADR Generation",
  "Architecture v2 Planner",
  "Diagram Update",
];

const navItems: Array<{ id: View; label: string; icon: typeof CircleDot }> = [
  { id: "overview", label: "Overview", icon: CircleDot },
  { id: "architecture", label: "Architecture", icon: Network },
  { id: "findings", label: "Findings", icon: AlertTriangle },
  { id: "adrs", label: "ADRs", icon: ScrollText },
  { id: "changes", label: "Changes", icon: GitCompare },
  { id: "json", label: "Raw JSON", icon: Braces },
];

export default function App() {
  const [file, setFile] = useState<File | null>(null);
  const [run, setRun] = useState<WorkflowRunResponse | null>(null);
  const [selectedView, setSelectedView] = useState<View>("overview");
  const [graphView, setGraphView] = useState<GraphView>("target");
  const [selectedFinding, setSelectedFinding] = useState<ReviewFinding | null>(null);
  const [selectedAdr, setSelectedAdr] = useState<ADR | null>(null);
  const [isRunning, setIsRunning] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [engine, setEngine] = useState("unknown");

  useEffect(() => {
    fetchHealth()
      .then((health) => setEngine(health.engine))
      .catch(() => setEngine("offline"));
  }, []);

  const result = run?.result ?? null;
  const summary = useMemo(() => {
    if (!result) {
      return null;
    }
    const critical = result.findings.filter((finding) => finding.severity === "critical").length;
    const high = result.findings.filter((finding) => finding.severity === "high").length;
    const diff = buildGraphDiff(result.architecture_v1, result.architecture_v2);
    return {
      components: result.architecture_v1.nodes.length,
      critical,
      high,
      adrs: result.adrs.length,
      changes:
        diff.addedNodes.length +
        diff.removedNodes.length +
        diff.changedAttributes.length +
        diff.addedConstraints.length +
        diff.removedConstraints.length +
        diff.addedEdges.length +
        diff.removedEdges.length,
    };
  }, [result]);

  function onFileChange(event: ChangeEvent<HTMLInputElement>) {
    const nextFile = event.target.files?.[0] ?? null;
    setFile(nextFile);
    setError(null);
  }

  async function runReview() {
    if (!file) {
      setError("Select a PDF, TXT, or MD document first.");
      return;
    }
    setIsRunning(true);
    setError(null);
    setSelectedView("overview");
    try {
      const response = await uploadArchitectureDocument(file);
      setRun(response);
      setSelectedFinding(response.result.findings[0] ?? null);
      setSelectedAdr(response.result.adrs[0] ?? null);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Review failed.");
    } finally {
      setIsRunning(false);
    }
  }

  return (
    <div className="app-shell">
      <header className="topbar">
        <div>
          <div className="eyebrow">OpenArchitect</div>
          <h1>Architecture Review Workspace</h1>
        </div>
        <div className="topbar-meta">
          <span>Runtime: LangGraph</span>
          <span>Provider: Gemini</span>
          <span>Engine: {engine}</span>
          {run ? <span>Run: {run.run_id.slice(0, 8)}</span> : null}
        </div>
      </header>

      <main className="workspace">
        <aside className="sidebar">
          {/* <section className="upload-panel"> */}
            {/* <label className="file-drop">
              <Upload size={20} />
              <span>{file ? file.name : "Select SAD file"}</span>
              <input accept=".pdf,.txt,.md" type="file" onChange={onFileChange} />
            </label>
            <button className="primary-button" disabled={isRunning} onClick={runReview} title="Run review">
              {isRunning ? <Loader2 className="spin" size={18} /> : <Play size={18} />}
              <span>{isRunning ? "Running" : "Run Review"}</span>
            </button>
            {error ? <div className="error-box">{error}</div> : null} */}
          {/* </section> */}
       
          <section className="stage-panel">
            {workflowStages.map((stage) => (
              <div className="stage-row" key={stage}>
                {isRunning ? <Loader2 className="spin muted" size={14} /> : <CheckCircle2 size={14} />}
                <span>{stage}</span>
              </div>
            ))}
          </section>
          <hr style={{ border: 'none', borderBottom: '0.1rem solid gray', marginTop: '2rem' }} />
          <nav className="side-nav">
            {navItems.map((item) => {
              const Icon = item.icon;
              return (
                <button
                  className={selectedView === item.id ? "nav-button active" : "nav-button"}
                  key={item.id}
                  onClick={() => setSelectedView(item.id)}
                  title={item.label}
                >
                  <Icon size={18} />
                  <span>{item.label}</span>
                </button>
              );
            })}
          </nav>
        </aside>

        <section className="main-panel">
          {!result ? (
            <EmptyState
              isRunning={isRunning}
              file={file}
              onFileChange={onFileChange}
              runReview={runReview}
              error={error}
            />
          ) : (
            <>
              {selectedView === "overview" ? <Overview result={result} summary={summary!} /> : null}
              {selectedView === "architecture" ? (
                <ArchitectureView graphView={graphView} onGraphViewChange={setGraphView} result={result} />
              ) : null}
              {selectedView === "findings" ? (
                <FindingsView
                  findings={result.findings}
                  selectedFinding={selectedFinding}
                  onSelectFinding={setSelectedFinding}
                />
              ) : null}
              {selectedView === "adrs" ? (
                <AdrsView adrs={result.adrs} selectedAdr={selectedAdr} onSelectAdr={setSelectedAdr} />
              ) : null}
              {selectedView === "changes" ? <ChangesView result={result} /> : null}
              {selectedView === "json" ? <RawJson run={run!} /> : null}
            </>
          )}
        </section>
      </main>
    </div>
  );
}

function EmptyState({
  isRunning,
  file,
  onFileChange,
  runReview,
  error,
}: {
  isRunning: boolean;
  file: File | null;
  onFileChange: (event: ChangeEvent<HTMLInputElement>) => void;
  runReview: () => void;
  error: string | null;
}) {
  return (
    <div className="empty-state">
      <div className="upload-center-card">
        {isRunning ? (
          <Loader2 className="spin" size={42} />
        ) : (
          <div/>
        )}

        <h2>
          {isRunning
            ? "Architecture Review Running"
            : "Upload a Software Architecture Document"}
        </h2>

        <label className="large-file-drop">
          <Upload size={38} />
          <span>{file ? file.name : "Select Architecture Document"}</span>
          <span><p>
            PDF, TXT and Markdown files are supported.
          </p></span>
          <input
            accept=".pdf,.txt,.md"
            type="file"
            onChange={onFileChange}
          />
        </label>

        <button
          className="primary-button large"
          disabled={isRunning}
          onClick={runReview}
        >
          {isRunning ? (
            <Loader2 className="spin" size={18} />
          ) : (
            <Play size={18} />
          )}

          <span>
            {isRunning ? "Running Review..." : "Run Review"}
          </span>
        </button>

        {error && (
          <div className="error-box">
            {error}
          </div>
        )}
      </div>
    </div>
  );
}

function Overview({
  result,
  summary,
}: {
  result: WorkflowRunResponse["result"];
  summary: Summary;
}) {
  const topFindings = result.findings.slice(0, 4);
  return (
    <div className="content-stack">
      <section className="metric-grid">
        <Metric label="Components" value={summary.components} />
        <Metric label="Critical" value={summary.critical} tone="critical" />
        <Metric label="High" value={summary.high} tone="high" />
        <Metric label="ADRs" value={summary.adrs} />
        <Metric label="Changes" value={summary.changes} />
      </section>
      <section className="two-column">
        <div className="panel-block">
          <h2>Top Risks</h2>
          <div className="item-list">
            {topFindings.map((finding) => (
              <div className="list-item" key={finding.id}>
                <SeverityBadge severity={finding.severity} />
                <div>
                  <strong>{finding.finding}</strong>
                  <span>{finding.agent_role}</span>
                </div>
              </div>
            ))}
          </div>
        </div>
        <div className="panel-block">
          <h2>Generated ADRs</h2>
          <div className="item-list">
            {result.adrs.slice(0, 5).map((adr) => (
              <div className="list-item" key={adr.id}>
                <span className="id-pill">{adr.id}</span>
                <div>
                  <strong>{adr.title}</strong>
                  <span>{adr.status}</span>
                </div>
              </div>
            ))}
          </div>
        </div>
      </section>
      <section className="panel-block">
        <h2>Target Diagram</h2>
        <MermaidDiagram chart={result.diagram.content} />
      </section>
    </div>
  );
}

function ArchitectureView({
  result,
  graphView,
  onGraphViewChange,
}: {
  result: WorkflowRunResponse["result"];
  graphView: GraphView;
  onGraphViewChange: (view: GraphView) => void;
}) {
  const graph = graphView === "current" ? result.architecture_v1 : result.architecture_v2;
  const chart = graphView === "current" ? graphToMermaid(result.architecture_v1) : result.diagram.content;

  return (
    <div className="content-stack">
      <div className="segmented">
        <button className={graphView === "current" ? "selected" : ""} onClick={() => onGraphViewChange("current")}>
          Current
        </button>
        <button className={graphView === "target" ? "selected" : ""} onClick={() => onGraphViewChange("target")}>
          Target
        </button>
      </div>
      <section className="panel-block">
        <MermaidDiagram chart={chart} />
      </section>
      <section className="three-column">
        <GraphCollection title="Nodes" items={graph.nodes.map((node) => `${node.id} (${node.type})`)} />
        <GraphCollection
          title="Edges"
          items={graph.edges.map((edge) => `${edge.from} -> ${edge.to} (${edge.relationship})`)}
        />
        <GraphCollection title="Constraints" items={graph.constraints} />
      </section>
    </div>
  );
}

function FindingsView({
  findings,
  selectedFinding,
  onSelectFinding,
}: {
  findings: ReviewFinding[];
  selectedFinding: ReviewFinding | null;
  onSelectFinding: (finding: ReviewFinding) => void;
}) {
  return (
    <div className="split-view">
      <div className="panel-block">
        <h2>Findings</h2>
        <div className="table-list">
          {findings.map((finding) => (
            <button
              className={selectedFinding?.id === finding.id ? "row-button active" : "row-button"}
              key={finding.id}
              onClick={() => onSelectFinding(finding)}
            >
              <SeverityBadge severity={finding.severity} />
              <span>{finding.id}</span>
              <strong>{finding.finding}</strong>
              <span>{finding.agent_role}</span>
            </button>
          ))}
        </div>
      </div>
      <DetailPanel title={selectedFinding?.id ?? "Finding"}>
        {selectedFinding ? (
          <FindingDetail finding={selectedFinding} />
        ) : (
          <p className="muted-copy">Select a finding.</p>
        )}
      </DetailPanel>
    </div>
  );
}

function AdrsView({
  adrs,
  selectedAdr,
  onSelectAdr,
}: {
  adrs: ADR[];
  selectedAdr: ADR | null;
  onSelectAdr: (adr: ADR) => void;
}) {
  return (
    <div className="split-view">
      <div className="panel-block">
        <h2>ADRs</h2>
        <div className="table-list">
          {adrs.map((adr) => (
            <button
              className={selectedAdr?.id === adr.id ? "row-button active" : "row-button"}
              key={adr.id}
              onClick={() => onSelectAdr(adr)}
            >
              <span className="id-pill">{adr.id}</span>
              <strong>{adr.title}</strong>
              <span>{adr.status}</span>
            </button>
          ))}
        </div>
      </div>
      <DetailPanel title={selectedAdr?.id ?? "ADR"}>
        {selectedAdr ? <AdrDetail adr={selectedAdr} /> : <p className="muted-copy">Select an ADR.</p>}
      </DetailPanel>
    </div>
  );
}

function ChangesView({ result }: { result: WorkflowRunResponse["result"] }) {
  const diff = buildGraphDiff(result.architecture_v1, result.architecture_v2);
  return (
    <div className="content-stack">
      <section className="panel-block">
        <h2>Node Changes</h2>
        <DiffList items={diff.addedNodes} prefix="+" tone="add" empty="No added nodes" />
        <DiffList items={diff.removedNodes} prefix="-" tone="remove" empty="No removed nodes" />
        <div className="change-list">
          {diff.changedAttributes.map((change) => (
            <div className="change-row" key={`${change.nodeId}-${change.key}`}>
              <strong>{change.nodeName}</strong>
              <span>{change.key}</span>
              <code>- {change.before}</code>
              <code>+ {change.after}</code>
            </div>
          ))}
        </div>
      </section>
      <section className="two-column">
        <div className="panel-block">
          <h2>Constraints</h2>
          <DiffList items={diff.removedConstraints} prefix="-" tone="remove" empty="No removed constraints" />
          <DiffList items={diff.addedConstraints} prefix="+" tone="add" empty="No added constraints" />
        </div>
        <div className="panel-block">
          <h2>Edges</h2>
          <DiffList items={diff.removedEdges} prefix="-" tone="remove" empty="No removed edges" />
          <DiffList items={diff.addedEdges} prefix="+" tone="add" empty="No added edges" />
        </div>
      </section>
    </div>
  );
}

function RawJson({ run }: { run: WorkflowRunResponse }) {
  return <pre className="json-view">{JSON.stringify(run, null, 2)}</pre>;
}

function Metric({
  label,
  value,
  tone,
}: {
  label: string;
  value: number;
  tone?: "critical" | "high";
}) {
  return (
    <div className={`metric ${tone ?? ""}`}>
      <span>{label}</span>
      <strong>{value}</strong>
    </div>
  );
}

function GraphCollection({ title, items }: { title: string; items: string[] }) {
  return (
    <div className="panel-block compact">
      <h2>{title}</h2>
      <div className="chip-list">
        {items.map((item) => (
          <span className="chip" key={item}>
            {item}
          </span>
        ))}
      </div>
    </div>
  );
}

function DetailPanel({ title, children }: { title: string; children: ReactNode }) {
  return (
    <aside className="detail-panel">
      <h2>{title}</h2>
      {children}
    </aside>
  );
}

function FindingDetail({ finding }: { finding: ReviewFinding }) {
  return (
    <div className="detail-stack">
      <SeverityBadge severity={finding.severity} />
      <p>{finding.finding}</p>
      <DetailList title="Evidence" items={finding.evidence} />
      <DetailList title="Affected Components" items={finding.affected_components} />
      <DetailList title="Recommendation" items={[finding.recommendation]} />
      <DetailList title="ADR" items={[finding.requires_adr ? "Required" : "Not required"]} />
    </div>
  );
}

function AdrDetail({ adr }: { adr: ADR }) {
  return (
    <div className="detail-stack">
      <p>{adr.context}</p>
      <DetailList title="Decision" items={[adr.decision]} />
      <DetailList title="Alternatives" items={adr.alternatives} />
      <DetailList title="Consequences" items={adr.consequences} />
      <DetailList title="Impacted Components" items={adr.impacted_components} />
      <DetailList title="Linked Findings" items={adr.linked_findings} />
      <DetailList title="Diagram Changes" items={adr.diagram_changes} />
    </div>
  );
}

function DetailList({ title, items }: { title: string; items: string[] }) {
  return (
    <div>
      <h3>{title}</h3>
      <ul className="detail-list">
        {(items.length > 0 ? items : ["None recorded"]).map((item) => (
          <li key={item}>{item}</li>
        ))}
      </ul>
    </div>
  );
}

function DiffList({
  items,
  prefix,
  tone,
  empty,
}: {
  items: string[];
  prefix: string;
  tone: "add" | "remove";
  empty: string;
}) {
  return (
    <div className="diff-list">
      {(items.length > 0 ? items : [empty]).map((item) => (
        <div className={`diff-row ${tone}`} key={`${prefix}-${item}`}>
          <span>{items.length > 0 ? prefix : ""}</span>
          <code>{item}</code>
        </div>
      ))}
    </div>
  );
}

function SeverityBadge({ severity }: { severity: string }) {
  return <span className={`severity ${severity}`}>{severity}</span>;
}
