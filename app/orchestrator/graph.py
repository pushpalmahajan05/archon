"""
ARCHON LangGraph Pipeline
Builds the sequential agent graph:

START → repository → architecture → historian → impact → security → synthesizer → END
"""
import logging

from langgraph.graph import StateGraph, END

from app.models.state import ArchonState
from app.agents.repository_agent import repository_agent
from app.agents.architecture_agent import architecture_agent
from app.agents.historian_agent import historian_agent
from app.agents.impact_agent import impact_agent
from app.agents.security_agent import security_agent
from app.agents.synthesizer_agent import synthesizer_agent

logger = logging.getLogger(__name__)


def build_graph():
    """
    Construct and compile the LangGraph StateGraph for ARCHON.
    Returns a compiled runnable graph.
    """
    builder = StateGraph(ArchonState)

    # Register all agent nodes
    builder.add_node("repository", repository_agent)
    builder.add_node("architecture", architecture_agent)
    builder.add_node("historian", historian_agent)
    builder.add_node("impact", impact_agent)
    builder.add_node("security", security_agent)
    builder.add_node("synthesizer", synthesizer_agent)

    # Sequential pipeline edges
    builder.set_entry_point("repository")
    builder.add_edge("repository", "architecture")
    builder.add_edge("architecture", "historian")
    builder.add_edge("historian", "impact")
    builder.add_edge("impact", "security")
    builder.add_edge("security", "synthesizer")
    builder.add_edge("synthesizer", END)

    return builder.compile()


# Singleton compiled graph
_graph = None


def get_graph():
    global _graph
    if _graph is None:
        _graph = build_graph()
    return _graph
