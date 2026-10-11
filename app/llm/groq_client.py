"""
Groq LLM Client
Uses the OpenAI-compatible Groq endpoint for all agent reasoning.
"""
import json
import logging
from typing import Optional

from openai import OpenAI

from app.config import settings

logger = logging.getLogger(__name__)

_client: Optional[OpenAI] = None


def _get_client() -> OpenAI:
    global _client
    if _client is None:
        _client = OpenAI(
            api_key=settings.groq_api_key,
            base_url="https://api.groq.com/openai/v1",
        )
    return _client


def ask_groq(system_prompt: str, user_prompt: str, temperature: float = 0.1) -> str:
    """
    Send a chat completion to Groq and return the text response.
    Falls back to a placeholder when the API key is not configured.
    """
    if settings.groq_api_key.startswith("PLACEHOLDER"):
        logger.warning("Groq API key not configured — returning mock response.")
        return _mock_response(user_prompt)

    try:
        client = _get_client()
        response = client.chat.completions.create(
            model=settings.groq_model,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
            temperature=temperature,
        )
        return response.choices[0].message.content or ""
    except Exception as e:
        logger.error("Groq API call failed: %s", e)
        raise


def ask_groq_json(system_prompt: str, user_prompt: str, temperature: float = 0.1) -> dict:
    """
    Ask Groq and parse the JSON response.
    Injects JSON-only instruction into the system prompt.
    """
    json_system = (
        system_prompt
        + "\n\nIMPORTANT: Respond ONLY with valid JSON. No explanatory text before or after."
    )

    if settings.groq_api_key.startswith("PLACEHOLDER"):
        logger.warning("Groq API key not configured — returning mock JSON response.")
        return _mock_json_response(user_prompt)

    raw = ask_groq(json_system, user_prompt, temperature)

    # Strip markdown code fences if present
    raw = raw.strip()
    if raw.startswith("```"):
        raw = raw.split("```")[1]
        if raw.startswith("json"):
            raw = raw[4:]
    raw = raw.strip()

    try:
        return json.loads(raw)
    except json.JSONDecodeError as e:
        logger.error("Failed to parse JSON from Groq: %s\nRaw: %s", e, raw)
        return {"error": str(e), "raw": raw}


def _mock_response(user_prompt: str) -> str:
    """Return a structured placeholder when no API key is set."""
    return f"""[MOCK RESPONSE - Configure GROQ_API_KEY to enable real analysis]

Query: {user_prompt[:200]}

This is a placeholder response generated because no Groq API key is configured.
The ARCHON system is fully wired up and ready — it will produce real evidence-backed
analysis once you add your API key to .env.

Components identified: [placeholder]
Confidence: 0.0
Evidence: None (placeholder mode)
"""


def _mock_json_response(user_prompt: str) -> dict:
    """Return a structured mock JSON when no API key is set."""
    return {
        "mode": "placeholder",
        "message": "Configure GROQ_API_KEY in .env to enable real analysis",
        "query": user_prompt[:100],
        "summary": "Placeholder response — API key not configured",
        "components": [],
        "evidence": [],
        "confidence": 0.0,
        "risks": [],
        "recommendation": "Add your Groq API key to .env and re-run the analysis.",
    }
