"""
Full end-to-end test of ARCHON.
Ingests a demo repository and runs an analysis query.

Usage:
    python scripts/test_archon.py
    python scripts/test_archon.py --repo redis-demo --query "Replace Redis with DynamoDB"
    python scripts/test_archon.py --repo flask --query "Replace Jinja2 with Mako" --report
"""
import sys
import os
import argparse
import json
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional, Dict, Any

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import logging
logging.basicConfig(level=logging.WARNING, format="%(levelname)s  %(message)s")


DEMO_REPO_URL = "https://github.com/redis/redis-py.git"
DEMO_QUERY = "What components depend on Redis, and what would be affected if Redis were replaced with an in-memory alternative?"


# ── Report helpers ─────────────────────────────────────────────────────────────

def _risk_emoji(level: str) -> str:
    level = str(level).upper()
    return {"CRITICAL": "🔴", "HIGH": "🔴", "MEDIUM": "🟡", "LOW": "🟢"}.get(level, "⚪")


def _confidence_bar(score: float) -> str:
    """Turn a 0-1 float into a simple visual percentage."""
    pct = int(round(score * 100)) if score <= 1.0 else int(round(score))
    return f"{pct}%"


def _expand_reasoning_with_groq(
    repo_name: str,
    user_query: str,
    raw_reasoning: str,
    decision_data: dict,
) -> str:
    """
    If the raw reasoning is very terse, ask Groq for a well-structured prose
    paragraph. Falls back to the raw reasoning if Groq is unavailable.
    """
    # Only call Groq if reasoning is too short to be useful
    if len(raw_reasoning.strip()) >= 200:
        return raw_reasoning.strip()

    try:
        from app.llm.groq_client import ask_groq

        system_prompt = (
            "You are a technical writer summarising a software architecture analysis. "
            "Write a concise but thorough reasoning paragraph (3-5 sentences) explaining "
            "WHY the recommendation was made, referencing the key evidence provided. "
            "Do NOT include section headers or bullet points — plain prose only."
        )
        user_prompt = (
            f"Repository: {repo_name}\n"
            f"Query: {user_query}\n"
            f"Recommendation: {decision_data.get('recommendation', '')}\n"
            f"Raw reasoning: {raw_reasoning}\n"
            f"Direct impacts: {json.dumps(decision_data.get('direct_impact', []))}\n"
            f"Security implications: {json.dumps(decision_data.get('security_implications', [])[:3])}\n"
            f"Historical context: {decision_data.get('historical_context', '')[:300]}\n\n"
            "Write the reasoning paragraph now."
        )
        return ask_groq(system_prompt, user_prompt, temperature=0.2).strip()
    except Exception as e:
        logging.getLogger(__name__).warning("Groq reasoning expansion failed: %s", e)
        return raw_reasoning.strip()


def generate_report(
    decision,          # ArchonDecision instance
    repo_name: str,
    user_query: str,
    ingestion_summary: Optional[Dict[str, Any]] = None,
    output_dir: Optional[Path] = None,
) -> Path:
    """
    Generate a Markdown analysis report from an ArchonDecision.

    Args:
        decision:          The ArchonDecision returned by run_analysis().
        repo_name:         Repository slug.
        user_query:        The original change-request query.
        ingestion_summary: Optional dict returned by ingest_repository().
        output_dir:        Where to write the file (defaults to project root).

    Returns:
        Path to the written .md file.
    """
    today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    session_id = decision.session_id or "unknown"

    # ── Sanitise query into a safe filename fragment ────────────────────────
    query_slug = re.sub(r"[^a-zA-Z0-9]+", "_", user_query[:60]).strip("_").lower()
    filename = f"analysis_{repo_name}_{query_slug[:40]}_{session_id}.md"

    if output_dir is None:
        output_dir = Path(__file__).parent.parent  # project root
    output_path = output_dir / filename

    # ── Confidence ──────────────────────────────────────────────────────────
    confidence_pct = _confidence_bar(decision.confidence)

    # ── Reasoning (expand if needed) ───────────────────────────────────────
    reasoning_text = _expand_reasoning_with_groq(
        repo_name,
        user_query,
        decision.reasoning or "",
        {
            "recommendation": decision.recommendation,
            "direct_impact": decision.direct_impact,
            "security_implications": decision.security_implications,
            "historical_context": decision.historical_context,
        },
    )

    lines = []

    # ── Header ──────────────────────────────────────────────────────────────
    lines.append(f"# ARCHON Analysis Report")
    lines.append(f"## Repository: {repo_name}")
    lines.append(f"## Query: {user_query}")
    lines.append("")
    lines.append("| Field | Value |")
    lines.append("|---|---|")
    lines.append(f"| **Session ID** | {session_id} |")
    lines.append(f"| **Processing Time** | {decision.processing_time_seconds}s |")
    lines.append(f"| **Confidence** | {confidence_pct} |")
    lines.append(f"| **Analysis Date** | {today} |")
    lines.append("")
    lines.append("---")
    lines.append("")

    # ── Recommendation ──────────────────────────────────────────────────────
    lines.append("## ✅ Recommendation")
    lines.append("")
    lines.append(f"> **{decision.recommendation}**")
    lines.append("")
    lines.append("---")
    lines.append("")

    # ── Reasoning ───────────────────────────────────────────────────────────
    lines.append("## 🧠 Reasoning")
    lines.append("")
    lines.append(reasoning_text)
    lines.append("")
    lines.append("---")
    lines.append("")

    # ── Impact ──────────────────────────────────────────────────────────────
    lines.append("## 💥 Impact")
    lines.append("")

    impact_findings = decision.agent_findings.get("impact", {})

    # Direct impact — try to use rich dicts from impact agent, fall back to strings
    raw_direct = impact_findings.get("direct_impact", decision.direct_impact or [])
    if raw_direct:
        lines.append("### Direct Impact")
        lines.append("")
        lines.append("| Component | Reason | Evidence |")
        lines.append("|---|---|---|")
        for item in raw_direct:
            if isinstance(item, dict):
                comp = item.get("component", item.get("name", str(item)))
                reason = item.get("reason", item.get("description", ""))
                evidence = item.get("evidence", item.get("file", ""))
            else:
                comp = str(item)
                reason = ""
                evidence = ""
            lines.append(f"| `{comp}` | {reason} | {evidence} |")
        lines.append("")

    # Indirect impact
    raw_indirect = impact_findings.get("indirect_impact", decision.indirect_impact or [])
    if raw_indirect:
        lines.append("### Indirect Impact")
        lines.append("")
        lines.append("| Component | Reason | Evidence |")
        lines.append("|---|---|---|")
        for item in raw_indirect:
            if isinstance(item, dict):
                comp = item.get("component", item.get("name", str(item)))
                reason = item.get("reason", item.get("description", ""))
                evidence = item.get("evidence", item.get("file", ""))
            else:
                comp = str(item)
                reason = ""
                evidence = ""
            lines.append(f"| `{comp}` | {reason} | {evidence} |")
        lines.append("")

    # API / config / testing / deployment impact (from impact agent findings)
    for section_key, section_title in [
        ("api_impact", "API Impact"),
        ("config_impact", "Configuration Impact"),
        ("testing_impact", "Testing Impact"),
        ("deployment_impact", "Deployment Impact"),
    ]:
        items = impact_findings.get(section_key, [])
        if items:
            lines.append(f"### {section_title}")
            lines.append("")
            if isinstance(items[0], dict):
                lines.append("| File / Area | Change Needed |")
                lines.append("|---|---|")
                for it in items:
                    f = it.get("file", it.get("component", ""))
                    c = it.get("change", it.get("description", str(it)))
                    lines.append(f"| `{f}` | {c} |")
            else:
                for it in items:
                    lines.append(f"- {it}")
            lines.append("")

    lines.append("---")
    lines.append("")

    # ── Security ─────────────────────────────────────────────────────────────
    if decision.security_implications or decision.risks:
        security_findings = decision.agent_findings.get("security", {})
        summary_line = security_findings.get("summary", "")
        lines.append("## 🔒 Security Implications")
        lines.append("")
        if summary_line:
            lines.append(f"> **Summary:** {summary_line}")
            lines.append("")

        # Data-flow changes from security agent
        data_flows = security_findings.get("data_flow_changes", [])
        if data_flows:
            lines.append("### Data Flow Changes")
            lines.append("")
            lines.append("| Description | Risk |")
            lines.append("|---|---|")
            for df in data_flows:
                if isinstance(df, dict):
                    desc = df.get("description", str(df))
                    risk = df.get("risk_level", df.get("risk", ""))
                    emoji = _risk_emoji(risk)
                    lines.append(f"| {desc} | {emoji} {risk} |")
                else:
                    lines.append(f"| {df} | |")
            lines.append("")

        if decision.security_implications and not data_flows:
            for si in decision.security_implications:
                lines.append(f"- {si}")
            lines.append("")

        # Risks table
        if decision.risks:
            lines.append("### Risks")
            lines.append("")
            lines.append("| Risk | Level | Mitigation |")
            lines.append("|---|---|---|")
            for r in decision.risks:
                if isinstance(r, dict):
                    desc = r.get("description", "")
                    level = r.get("level", "")
                    mitigation = r.get("mitigation", "")
                    emoji = _risk_emoji(level)
                    lines.append(f"| {desc} | {emoji} **{level}** | {mitigation} |")
                else:
                    lines.append(f"| {r} | | |")
            lines.append("")

        lines.append("---")
        lines.append("")

    # ── Historical context ────────────────────────────────────────────────────
    if decision.historical_context:
        history_findings = decision.agent_findings.get("history", {})
        lines.append("## 📜 Historical Context")
        lines.append("")
        lines.append(decision.historical_context)
        lines.append("")

        # Key commits from history agent
        commits = history_findings.get("key_commits", history_findings.get("commits", []))
        if commits:
            lines.append("**Evidence from commits:**")
            for c in commits[:5]:
                if isinstance(c, dict):
                    h = c.get("hash", c.get("id", ""))[:10]
                    msg = c.get("message", c.get("summary", ""))
                    lines.append(f"- `{h}` — *\"{msg}\"*")
                else:
                    lines.append(f"- {c}")
            lines.append("")

        # ADRs / evidence strength
        adrs = history_findings.get("adrs", [])
        evidence_strength = history_findings.get("evidence_strength", "UNKNOWN")
        lines.append(f"> **Evidence Strength:** {evidence_strength}"
                     + (" — no explicit ADR found, rationale inferred from code and commit history" if not adrs else ""))
        lines.append("")
        lines.append("---")
        lines.append("")

    # ── Alternatives ─────────────────────────────────────────────────────────
    if decision.alternatives:
        lines.append("## 🔀 Alternatives")
        lines.append("")
        for i, alt in enumerate(decision.alternatives, 1):
            marker = " *(recommended)*" if i == 1 else ""
            lines.append(f"{i}. **{alt}**{marker}")
        lines.append("")
        lines.append("---")
        lines.append("")

    # ── Evidence trail ────────────────────────────────────────────────────────
    if decision.evidence:
        lines.append("## 📋 Evidence Trail")
        lines.append("")
        lines.append("| # | Type | Source | Content |")
        lines.append("|---|---|---|---|")
        for i, ev in enumerate(decision.evidence, 1):
            if isinstance(ev, dict):
                ev_type = ev.get("type", ev.get("source_type", ""))
                source = ev.get("source", ev.get("file", ""))
                content = str(ev.get("content", ev.get("summary", "")))[:100]
            else:
                ev_type = ""
                source = ""
                content = str(ev)[:100]
            lines.append(f"| {i} | {ev_type} | `{source}` | {content} |")
        lines.append("")
        lines.append("---")
        lines.append("")

    # ── Uncertainties ─────────────────────────────────────────────────────────
    if decision.uncertainties:
        lines.append("## ❓ Uncertainties")
        lines.append("")
        for i, u in enumerate(decision.uncertainties, 1):
            lines.append(f"{i}. {u}")
        lines.append("")
        lines.append("---")
        lines.append("")

    # ── Agent confidence scores ───────────────────────────────────────────────
    lines.append("## 📊 Agent Confidence Scores")
    lines.append("")
    lines.append("| Agent | Confidence |")
    lines.append("|---|---|")

    agent_conf_map = {
        "repository":    ("Repository Intelligence", decision.agent_findings.get("repository", {})),
        "architecture":  ("Architecture Reconstruction", decision.agent_findings.get("architecture", {})),
        "history":       ("Decision Historian", decision.agent_findings.get("history", {})),
        "impact":        ("Change Impact", decision.agent_findings.get("impact", {})),
        "security":      ("Security Analysis", decision.agent_findings.get("security", {})),
    }
    for _key, (label, findings) in agent_conf_map.items():
        conf = findings.get("confidence", None)
        if conf is not None:
            note = ""
            if _key == "history":
                adrs = findings.get("adrs", [])
                if not adrs:
                    note = " *(no ADR found — rationale inferred)*"
            lines.append(f"| {label} | {_confidence_bar(float(conf))}{note} |")

    lines.append(f"| **Decision Synthesizer (Final)** | **{confidence_pct}** |")
    lines.append("")

    reason_for_low_conf = ""
    hist_findings = decision.agent_findings.get("history", {})
    if decision.confidence < 0.7 and not hist_findings.get("adrs", []):
        reason_for_low_conf = (
            "> The overall confidence is moderate primarily because no explicit ADR was found "
            "for the original decision. The technical and security evidence is strong, "
            "but the historical rationale remains partially inferred."
        )
    if reason_for_low_conf:
        lines.append(reason_for_low_conf)
        lines.append("")
    lines.append("---")
    lines.append("")

    # ── Architecture summary ──────────────────────────────────────────────────
    arch_findings = decision.agent_findings.get("architecture", {})
    if arch_findings or ingestion_summary:
        lines.append("## 🏗 Architecture Summary")
        lines.append("")

        if ingestion_summary:
            lines.append("| Metric | Count |")
            lines.append("|---|---|")
            metric_map = [
                ("files_total",    "Files indexed"),
                ("functions",      "Functions parsed"),
                ("classes",        "Classes parsed"),
                ("imports",        "Import relationships"),
                ("dependencies",   "Dependencies"),
                ("commits_new",    "Commits indexed"),
                ("vectors_added",  "Vector chunks (Qdrant)"),
                ("adrs",           "ADRs found"),
            ]
            for key, label in metric_map:
                val = ingestion_summary.get(key)
                if val is not None:
                    lines.append(f"| {label} | {val} |")
            lines.append("")

        arch_style = arch_findings.get("architectural_style", arch_findings.get("style", ""))
        if arch_style:
            lines.append(f"**Architectural Style:** {arch_style}")
            lines.append("")

        components = arch_findings.get("key_components", arch_findings.get("components", []))
        if components:
            lines.append("**Key Components:**")
            for comp in components[:8]:
                if isinstance(comp, dict):
                    name = comp.get("name", "")
                    desc = comp.get("description", comp.get("role", ""))
                    lines.append(f"- `{name}` — {desc}")
                else:
                    lines.append(f"- {comp}")
            lines.append("")

        lines.append("---")
        lines.append("")

    # ── Footer ───────────────────────────────────────────────────────────────
    from app.config import settings
    lines.append(
        f"*Generated by ARCHON — Agentic Change-Impact Analysis System*  "
    )
    lines.append(
        f"*Model: {settings.groq_model} via Groq | "
        f"Embeddings: all-MiniLM-L6-v2 | Graph: Neo4j | Vectors: Qdrant*"
    )
    lines.append("")

    report_md = "\n".join(lines)

    output_path.write_text(report_md, encoding="utf-8")
    return output_path


# ── Main ───────────────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(description="Run a full ARCHON analysis")
    parser.add_argument("--repo", default=None, help="Repository name (must be ingested already, or use --url)")
    parser.add_argument("--url", default=None, help="Clone and ingest this URL first")
    parser.add_argument("--local", default=None, help="Use this local path")
    parser.add_argument("--query", default=DEMO_QUERY, help="Change request query")
    parser.add_argument("--ingest", action="store_true", help="Run ingestion before analysis")
    parser.add_argument("--report", action="store_true", help="Generate a Markdown analysis report after the run")
    parser.add_argument("--report-dir", default=None, help="Directory to save the report (default: project root)")
    args = parser.parse_args()

    from app.config import settings

    ingestion_summary: Optional[Dict[str, Any]] = None

    # ── Step 1: Ingest if requested ──────────────────────────────────────────
    if args.ingest or args.url:
        from app.ingestion.repository_loader import clone_repository, get_local_repo
        from app.ingestion.indexer import ingest_repository
        from pathlib import Path

        if args.url:
            url = args.url
            name = args.repo or url.rstrip("/").split("/")[-1].replace(".git", "")
            print(f"\n  Cloning {url}...")
            repo_path = clone_repository(url, name)
        elif args.local:
            repo_path = get_local_repo(args.local)
            name = args.repo or repo_path.name
        else:
            print("  ✗  Provide --url or --local to ingest.")
            sys.exit(1)

        print(f"  Ingesting {name}...")
        ingestion_summary = ingest_repository(repo_path, name)
        summary = ingestion_summary
        print(f"  ✓  Ingested: {summary['files_total']} files, {summary['vectors_added']} vectors")
        repo_name = name

    elif args.local:
        from pathlib import Path
        from app.ingestion.repository_loader import get_local_repo
        from app.ingestion.indexer import ingest_repository

        repo_path = get_local_repo(args.local)
        repo_name = args.repo or repo_path.name
        print(f"  Ingesting local repo {repo_name}...")
        ingestion_summary = ingest_repository(repo_path, repo_name)
        summary = ingestion_summary
        print(f"  ✓  Ingested: {summary['files_total']} files, {summary['vectors_added']} vectors")

    elif args.repo:
        repo_name = args.repo
    else:
        # Default: use any already-ingested repo
        repos_dir = settings.repos_dir
        if repos_dir.exists():
            repos = [d.name for d in repos_dir.iterdir() if d.is_dir()]
        else:
            repos = []

        if repos:
            repo_name = repos[0]
            print(f"  Using existing repository: {repo_name}")
        else:
            print("  No repositories ingested yet.")
            print("  Run: python scripts/test_archon.py --url https://github.com/redis/redis-py.git --ingest")
            sys.exit(0)

    # ── Step 2: Run analysis ─────────────────────────────────────────────────
    from app.orchestrator.orchestrator import run_analysis

    print(f"\n{'='*60}")
    print(f"  ARCHON Analysis")
    print(f"{'='*60}")
    print(f"  Repository : {repo_name}")
    print(f"  Query      : {args.query}")
    print(f"{'='*60}\n")

    decision = run_analysis(
        repository_name=repo_name,
        user_query=args.query,
    )

    # ── Step 3: Display results ──────────────────────────────────────────────
    print(f"\n{'='*60}")
    print("  RECOMMENDATION")
    print(f"{'='*60}")
    print(f"  {decision.recommendation}\n")

    print("  REASONING")
    print(f"  {decision.reasoning[:400] if decision.reasoning else 'N/A'}\n")

    if decision.direct_impact:
        print("  DIRECT IMPACT")
        for c in decision.direct_impact:
            print(f"    • {c}")
        print()

    if decision.indirect_impact:
        print("  INDIRECT IMPACT")
        for c in decision.indirect_impact:
            print(f"    • {c}")
        print()

    if decision.security_implications:
        print("  SECURITY IMPLICATIONS")
        for s in decision.security_implications[:3]:
            print(f"    • {s}")
        print()

    if decision.risks:
        print("  RISKS")
        for r in decision.risks[:3]:
            if isinstance(r, dict):
                print(f"    [{r.get('level','?')}] {r.get('description','')}")
            else:
                print(f"    • {r}")
        print()

    if decision.alternatives:
        print("  ALTERNATIVES")
        for alt in decision.alternatives[:3]:
            print(f"    • {alt}")
        print()

    if decision.historical_context:
        print("  HISTORICAL CONTEXT")
        print(f"  {decision.historical_context[:300]}\n")

    if decision.evidence:
        print("  EVIDENCE")
        for ev in decision.evidence[:4]:
            if isinstance(ev, dict):
                print(f"    [{ev.get('type','?')}] {ev.get('source','?')}: {str(ev.get('content',''))[:80]}")
            else:
                print(f"    • {ev}")
        print()

    if decision.uncertainties:
        print("  UNCERTAINTIES")
        for u in decision.uncertainties[:3]:
            print(f"    • {u}")
        print()

    print(f"{'='*60}")
    print(f"  Confidence          : {decision.confidence:.2f}")
    print(f"  Processing time     : {decision.processing_time_seconds}s")
    print(f"  Session ID          : {decision.session_id}")
    if decision.agent_findings.get("repository"):
        mode = decision.agent_findings["repository"].get("mode", "live")
        if mode == "placeholder":
            print(f"\n  ⚠  Running in PLACEHOLDER mode — add GROQ_API_KEY to .env for real analysis")
    print(f"{'='*60}\n")

    # ── Step 4: Generate Markdown report ────────────────────────────────────
    if args.report:
        report_dir = Path(args.report_dir) if args.report_dir else None
        print("  Generating Markdown report...")
        report_path = generate_report(
            decision=decision,
            repo_name=repo_name,
            user_query=args.query,
            ingestion_summary=ingestion_summary,
            output_dir=report_dir,
        )
        print(f"  ✓  Report saved to: {report_path}\n")


if __name__ == "__main__":
    main()
