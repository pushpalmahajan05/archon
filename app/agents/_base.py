"""
Base Agent Utilities
Shared helpers for all ARCHON agents.
"""
import json
import logging
from pathlib import Path
from typing import Any, Dict

logger = logging.getLogger(__name__)

_PROMPTS_DIR = Path(__file__).parent.parent / "prompts"


def load_prompt(name: str) -> str:
    """Load a prompt from the prompts directory."""
    path = _PROMPTS_DIR / f"{name}.md"
    if path.exists():
        return path.read_text(encoding="utf-8")
    logger.warning("Prompt file not found: %s", path)
    return f"You are the {name} agent of ARCHON."


def safe_json_parse(text: str, fallback: Dict) -> Dict[str, Any]:
    """Parse JSON from LLM output, returning fallback on failure."""
    if not text:
        return fallback
    # Strip markdown fences
    stripped = text.strip()
    if stripped.startswith("```"):
        parts = stripped.split("```")
        stripped = parts[1] if len(parts) > 1 else stripped
        if stripped.startswith("json"):
            stripped = stripped[4:]
    try:
        return json.loads(stripped.strip())
    except json.JSONDecodeError:
        # Try to extract the first {...} block
        start = stripped.find("{")
        end = stripped.rfind("}")
        if start != -1 and end != -1:
            try:
                return json.loads(stripped[start : end + 1])
            except Exception:
                pass
        logger.warning("Could not parse JSON from agent output: %s", stripped[:200])
        return {**fallback, "raw_response": text[:1000]}
