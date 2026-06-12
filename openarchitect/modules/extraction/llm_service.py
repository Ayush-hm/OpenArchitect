import json
import re

from pydantic import BaseModel

from openarchitect.core.contracts.model_provider import ModelProvider
from openarchitect.core.schemas import ArchitectureEdge, ArchitectureGraph
from openarchitect.modules.extraction.service import extract_architecture
from openarchitect.modules.extraction.critic_service import critique_architecture_graph
from openarchitect.modules.extraction.validation import validate_architecture_graph
from openarchitect.observability import traceable_step


class ArchitectureGraphOutput(BaseModel):
    architecture: ArchitectureGraph


@traceable_step(name="Extract Architecture With LLM", run_type="chain")
async def extract_architecture_with_llm(
    document_text: str,
    model_provider: ModelProvider,
) -> ArchitectureGraph:
    prompt = f"""
Extract an evidence-bound software architecture graph from the SAD.

Hard rules:
- Include only explicitly mentioned components.
- Do not invent components. Do not include headings as nodes.
- Merge Postgres/PostgreSQL/database/DB when they refer to the same store.
- Each node and edge needs a short evidence quote from the SAD.
- Allowed node types: user, service, data_store, cache, queue, external_system, worker, unknown.
- Allowed relationships: routes_to, authenticates, calls, reads_from, writes_to, stores_in, uses_storage, publishes, subscribes_to, depends_on, uses.
- Constraints should include facts such as single-AZ, single instance, no autoscaling, disabled encryption, public subnet, no DR, undefined RTO/RPO.

SAD text:
{document_text[:12000]}

Return only valid JSON in this exact shape:
{{
  "architecture": {{
    "nodes": [
      {{
        "id": "kebab-case-id",
        "name": "Component Name",
        "type": "user|service|data_store|cache|queue|external_system|worker|unknown",
        "description": null,
        "evidence": ["short exact quote from SAD"],
        "confidence": 0.9,
        "attributes": {{}}
      }}
    ],
    "edges": [
      {{
        "from": "source-node-id",
        "to": "target-node-id",
        "relationship": "routes_to|authenticates|calls|reads_from|writes_to|stores_in|uses_storage|publishes|subscribes_to|depends_on|uses",
        "description": null,
        "evidence": ["short exact quote from SAD"],
        "confidence": 0.9
      }}
    ],
    "constraints": ["constraint from SAD"],
    "unknowns": ["missing or unclear fact"]
  }}
}}
"""
    text = await model_provider.generate_text(prompt)
    output = ArchitectureGraphOutput.model_validate(_extract_json_object(text))
    validated = validate_architecture_graph(output.architecture, document_text, require_evidence=True)
    repaired = _repair_missing_edges(validated, document_text)
    criticized = await critique_architecture_graph(repaired, document_text, model_provider)
    return validate_architecture_graph(criticized, document_text, require_evidence=True)


def _repair_missing_edges(graph: ArchitectureGraph, document_text: str) -> ArchitectureGraph:
    repaired = extract_architecture(document_text)
    node_ids = {node.id for node in graph.nodes}
    existing = {(edge.from_node, edge.to_node, edge.relationship) for edge in graph.edges}

    for edge in repaired.edges:
        key = (edge.from_node, edge.to_node, edge.relationship)
        if edge.from_node not in node_ids or edge.to_node not in node_ids or key in existing:
            continue
        graph.edges.append(
            ArchitectureEdge(
                **{
                    "from": edge.from_node,
                    "to": edge.to_node,
                    "relationship": edge.relationship,
                    "description": edge.description,
                    "evidence": [edge.description] if edge.description else [],
                }
            )
        )
        existing.add(key)

    return graph


def _extract_json_object(text: str):
    stripped = text.strip()
    fenced = re.search(r"```(?:json)?\s*(.*?)```", stripped, re.DOTALL | re.IGNORECASE)
    if fenced:
        stripped = fenced.group(1).strip()

    try:
        return json.loads(stripped)
    except json.JSONDecodeError:
        start = stripped.find("{")
        end = stripped.rfind("}")
        if start >= 0 and end > start:
            return json.loads(stripped[start : end + 1])
        raise
