"""
Run ARCHON analysis with real-time orchestrator state tracking.
Captures and logs every state change as each agent is invoked by the orchestrator.
Generates a detailed Markdown report with the findings and all state transitions.
"""
import sys
import os
import argparse
import json
import time
import uuid
import copy
from datetime import datetime, timezone
from pathlib import Path

# Add project root to sys.path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from app.config import settings
from app.models.state import ArchonState
from app.models.decision import ArchonDecision
from app.orchestrator.graph import get_graph


def run_tracked_analysis(repository_name: str, user_query: str, repo_path: str = ""):
    session_id = str(uuid.uuid4())[:8]
    started_at = datetime.now(timezone.utc).isoformat()

    print(f"\n{'='*70}")
    print(f"  ARCHON Orchestrator: State-Tracked Execution Pipeline")
    print(f"{'='*70}")
    print(f"  Session ID   : {session_id}")
    print(f"  Repository   : {repository_name}")
    print(f"  User Query   : {user_query}")
    print(f"  Started At   : {started_at}")
    print(f"{'='*70}\n")

    initial_state: ArchonState = {
        "repository_path": repo_path,
        "repository_name": repository_name,
        "user_query": user_query,
        "plan": [
            "repository",
            "architecture",
            "historian",
            "impact",
            "security",
            "synthesizer",
        ],
        "repository_findings": {},
        "architecture_findings": {},
        "history_findings": {},
        "impact_findings": {},
        "security_findings": {},
        "final_decision": {},
        "evidence": [],
        "errors": [],
        "session_id": session_id,
        "started_at": started_at,
    }

    state_transitions = []
    
    # Record initial state transition
    state_transitions.append({
        "step": 0,
        "transition": "ORCHESTRATOR_INIT -> repository",
        "agent": "orchestrator",
        "timestamp": started_at,
        "duration_sec": 0.0,
        "state_delta": {
            "session_id": session_id,
            "repository_name": repository_name,
            "user_query": user_query,
            "plan": initial_state["plan"],
        },
        "cumulative_keys": list(initial_state.keys()),
        "summary": "Initialized shared state container and pipeline schedule."
    })

    graph = get_graph()
    current_state = copy.deepcopy(initial_state)
    start_total_time = time.time()

    pipeline_steps = ["repository", "architecture", "historian", "impact", "security", "synthesizer"]
    step_num = 1

    for step_output in graph.stream(initial_state):
        step_end_time = time.time()
        now_iso = datetime.now(timezone.utc).isoformat()

        # step_output is { node_name: updated_state }
        for node_name, updated_state in step_output.items():
            duration = round(step_end_time - start_total_time, 2)
            next_agent = pipeline_steps[step_num] if step_num < len(pipeline_steps) else "END"
            transition_name = f"{node_name} -> {next_agent}"

            print(f"\n{'─'*70}")
            print(f"  [ORCHESTRATOR STATE CHANGE #{step_num}] Agent: '{node_name.upper()}'")
            print(f"  Transition : {transition_name}")
            print(f"  Timestamp  : {now_iso}")
            print(f"{'─'*70}")

            # Identify delta
            delta = {}
            if node_name == "repository":
                delta["repository_findings"] = updated_state.get("repository_findings", {})
                print(f"  Components identified : {len(delta['repository_findings'].get('components', []))}")
                print(f"  Confidence            : {delta['repository_findings'].get('confidence', 0.0)}")
                print(f"  Observations          : {delta['repository_findings'].get('observations', '')[:120]}...")
            elif node_name == "architecture":
                delta["architecture_findings"] = updated_state.get("architecture_findings", {})
                print(f"  Architecture layers   : {len(delta['architecture_findings'].get('layers', []))}")
                print(f"  Data stores           : {delta['architecture_findings'].get('data_stores', [])}")
                print(f"  Confidence            : {delta['architecture_findings'].get('confidence', 0.0)}")
            elif node_name == "historian":
                delta["history_findings"] = updated_state.get("history_findings", {})
                print(f"  ADRs identified       : {len(delta['history_findings'].get('adrs', []))}")
                print(f"  Historical Rationale  : {delta['history_findings'].get('rationale', '')[:120]}...")
                print(f"  Confidence            : {delta['history_findings'].get('confidence', 0.0)}")
            elif node_name == "impact":
                delta["impact_findings"] = updated_state.get("impact_findings", {})
                direct = [c.get("component", str(c)) if isinstance(c, dict) else str(c) for c in delta["impact_findings"].get("direct_impact", [])]
                indirect = [c.get("component", str(c)) if isinstance(c, dict) else str(c) for c in delta["impact_findings"].get("indirect_impact", [])]
                print(f"  Direct Impact         : {len(direct)} components ({', '.join(direct[:4])})")
                print(f"  Indirect Impact       : {len(indirect)} components ({', '.join(indirect[:4])})")
                print(f"  Confidence            : {delta['impact_findings'].get('confidence', 0.0)}")
            elif node_name == "security":
                delta["security_findings"] = updated_state.get("security_findings", {})
                risks = delta["security_findings"].get("risks", [])
                print(f"  Security risks found  : {len(risks)}")
                for r in risks[:2]:
                    if isinstance(r, dict):
                        print(f"    [{r.get('level','?')}] {r.get('description','')[:80]}")
                print(f"  Confidence            : {delta['security_findings'].get('confidence', 0.0)}")
            elif node_name == "synthesizer":
                delta["final_decision"] = updated_state.get("final_decision", {})
                rec = delta["final_decision"].get("recommendation", "")
                conf = delta["final_decision"].get("confidence", 0.0)
                print(f"  Final Recommendation  : {rec[:140]}...")
                print(f"  Confidence            : {conf}")

            # Merge updated state
            current_state = copy.deepcopy(updated_state)

            state_transitions.append({
                "step": step_num,
                "transition": transition_name,
                "agent": node_name,
                "timestamp": now_iso,
                "duration_sec": duration,
                "state_delta": delta,
                "errors": updated_state.get("errors", []),
                "summary": f"Completed analysis for '{node_name}'. State updated."
            })

            step_num += 1

    total_time = round(time.time() - start_total_time, 2)
    decision_raw = current_state.get("final_decision", {})

    decision = ArchonDecision(
        query=user_query,
        repository=repository_name,
        recommendation=decision_raw.get(
            "recommendation",
            "Analysis could not be completed. Check errors.",
        ),
        reasoning=decision_raw.get("reasoning", ""),
        alternatives=[
            alt.get("option", str(alt)) if isinstance(alt, dict) else str(alt)
            for alt in decision_raw.get("alternatives", [])
        ],
        affected_components=decision_raw.get("affected_components", []),
        direct_impact=[
            item.get("component", str(item)) if isinstance(item, dict) else str(item)
            for item in current_state.get("impact_findings", {}).get("direct_impact", [])
        ],
        indirect_impact=[
            item.get("component", str(item)) if isinstance(item, dict) else str(item)
            for item in current_state.get("impact_findings", {}).get("indirect_impact", [])
        ],
        historical_context=decision_raw.get("historical_context", ""),
        security_implications=decision_raw.get("security_implications", []),
        risks=decision_raw.get("risks", []),
        evidence=decision_raw.get("evidence", []),
        uncertainties=decision_raw.get("uncertainties", []),
        confidence=float(decision_raw.get("confidence", 0.0)),
        agent_findings=decision_raw.get("agent_findings", {}),
        session_id=session_id,
        processing_time_seconds=total_time,
    )

    print(f"\n{'='*70}")
    print(f"  ORCHESTRATION PIPELINE COMPLETE")
    print(f"  Total Steps Execution : {step_num - 1}")
    print(f"  Total Duration        : {total_time}s")
    print(f"  Confidence            : {decision.confidence:.2f}")
    print(f"{'='*70}\n")

    return current_state, decision, state_transitions


def generate_markdown_report(
    current_state: ArchonState,
    decision: ArchonDecision,
    state_transitions: list,
    output_path: str,
):
    now_date = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    md = []
    md.append(f"# ARCHON Architectural Analysis Report")
    md.append(f"## Repository: `{decision.repository}`")
    md.append(f"## Query: `{decision.query}`\n")

    md.append("| Metadata | Details |")
    md.append("|---|---|")
    md.append(f"| **Session ID** | `{decision.session_id}` |")
    md.append(f"| **Processing Time** | {decision.processing_time_seconds:.2f} seconds |")
    md.append(f"| **Confidence Score** | **{int(decision.confidence * 100)}%** ({decision.confidence:.2f}) |")
    md.append(f"| **Date of Execution** | {now_date} |")
    md.append(f"| **Pipeline Type** | Multi-Agent Sequential LangGraph (6 Agents) |")
    md.append(f"| **Knowledge Bases** | Neo4j Graph DB + Qdrant Vector DB |")
    md.append(f"| **Inference Engine** | Groq (`{settings.groq_model}`) |\n")
    md.append("---\n")

    md.append("## 1. Executive Recommendation\n")
    md.append(f"> {decision.recommendation}\n")

    md.append("## 2. Architectural Reasoning & Technical Evaluation\n")
    md.append(f"{decision.reasoning}\n")

    # Affected components
    if decision.affected_components:
        md.append("### Affected Code Components\n")
        for comp in decision.affected_components:
            md.append(f"- `{comp}`")
        md.append("")

    # Direct & Indirect Impact
    md.append("## 3. Impact Analysis\n")
    md.append("### Direct Impact\n")
    impact_findings = current_state.get("impact_findings", {})
    direct_list = impact_findings.get("direct_impact", [])
    if direct_list:
        md.append("| Component | Reason / Evidence |")
        md.append("|---|---|")
        for item in direct_list:
            if isinstance(item, dict):
                comp = item.get("component", "Unknown")
                desc = item.get("description", item.get("reason", "Direct dependency"))
                md.append(f"| `{comp}` | {desc} |")
            else:
                md.append(f"| `{item}` | Directly referenced data structure |")
        md.append("")
    else:
        for c in decision.direct_impact:
            md.append(f"- `{c}`")
        md.append("")

    md.append("### Indirect Impact\n")
    indirect_list = impact_findings.get("indirect_impact", [])
    if indirect_list:
        md.append("| Component | Reason / Cascade Effect |")
        md.append("|---|---|")
        for item in indirect_list:
            if isinstance(item, dict):
                comp = item.get("component", "Unknown")
                desc = item.get("description", item.get("reason", "Indirect cascading dependency"))
                md.append(f"| `{comp}` | {desc} |")
            else:
                md.append(f"| `{item}` | Cascading dependency |")
        md.append("")
    else:
        for c in decision.indirect_impact:
            md.append(f"- `{c}`")
        md.append("")

    # Security Implications
    md.append("## 4. Security & Safety Implications\n")
    if decision.security_implications:
        for s in decision.security_implications:
            md.append(f"- {s}")
        md.append("")

    if decision.risks:
        md.append("### Identified Risk Matrix\n")
        md.append("| Severity | Risk Description | Mitigation |")
        md.append("|---|---|---|")
        for r in decision.risks:
            if isinstance(r, dict):
                lvl = r.get("level", "MEDIUM")
                desc = r.get("description", "")
                mit = r.get("mitigation", "Code review & rigorous test coverage")
                badge = "🔴" if lvl.upper() == "HIGH" else ("🟡" if lvl.upper() == "MEDIUM" else "🟢")
                md.append(f"| {badge} **{lvl.upper()}** | {desc} | {mit} |")
            else:
                md.append(f"| 🟡 **MEDIUM** | {r} | Add defensive checks |")
        md.append("")

    # Alternatives
    md.append("## 5. Feasible Architectural Alternatives\n")
    if decision.alternatives:
        for idx, alt in enumerate(decision.alternatives, 1):
            md.append(f"{idx}. {alt}")
        md.append("")

    # Historical Context
    md.append("## 6. Historical Context & Design Rationale\n")
    if decision.historical_context:
        md.append(f"{decision.historical_context}\n")
    else:
        md.append("No explicit ADRs documented; decisions inferred from commits and codebase structure.\n")

    # Evidence
    if decision.evidence:
        md.append("## 7. Knowledge Base Evidence Trail\n")
        for ev in decision.evidence:
            if isinstance(ev, dict):
                ev_type = ev.get("type", "code")
                src = ev.get("source", "repo")
                content = ev.get("content", "")
                md.append(f"- **[{ev_type.upper()}]** `{src}`: {content}")
            else:
                md.append(f"- {ev}")
        md.append("")

    # Uncertainties
    if decision.uncertainties:
        md.append("## 8. Uncertainties & Assumptions\n")
        for u in decision.uncertainties:
            md.append(f"- ❓ {u}")
        md.append("")

    # ── Section 9: Step-by-Step Orchestrator State Transitions ─────────────────
    md.append("---\n")
    md.append("## 9. Orchestrator State Machine Transitions\n")
    md.append("This section records every state transition as the LangGraph Orchestrator dispatched work across the specialized agents.\n")

    for t in state_transitions:
        step = t["step"]
        agent = t["agent"].upper()
        trans = t["transition"]
        ts = t["timestamp"]
        dur = t["duration_sec"]
        summary = t.get("summary", "")

        md.append(f"### 📍 Step {step}: `{trans}` ({agent})")
        md.append(f"- **Timestamp:** `{ts}`")
        md.append(f"- **Elapsed Time:** `{dur}s`")
        md.append(f"- **Summary:** {summary}")
        
        delta = t.get("state_delta", {})
        if delta:
            md.append("\n**State Update Payload (Delta):**")
            md.append("```json")
            md.append(json.dumps(delta, indent=2))
            md.append("```\n")

    # Write file
    content = "\n".join(md)
    out_file = Path(output_path)
    out_file.write_text(content, encoding="utf-8")
    print(f"\n[✓] Markdown Report generated at: {out_file.resolve()}")
    return content


def main():
    parser = argparse.ArgumentParser(description="Run state-tracked ARCHON analysis")
    parser.add_argument("--repo", default="pharmacy_management_Linked_Lists")
    parser.add_argument("--query", default="Can I replace linked lists with B-Trees.")
    parser.add_argument("--out", default="analysis_pharmacy_management_linked_lists_to_btrees.md")
    args = parser.parse_args()

    repo_path = str((settings.repos_dir / args.repo).resolve())
    current_state, decision, state_transitions = run_tracked_analysis(
        repository_name=args.repo,
        user_query=args.query,
        repo_path=repo_path,
    )

    generate_markdown_report(current_state, decision, state_transitions, args.out)


if __name__ == "__main__":
    main()
