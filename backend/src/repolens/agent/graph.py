"""LangGraph agent — cyclic state machine with search_code, query_graph, read_file tools.

The agent decides which tool to use (or to answer directly), executes it,
and loops until it has enough context or hits a guard limit.
"""

from typing import Any, Literal

import structlog
from langchain_anthropic import ChatAnthropic
from langchain_core.messages import AIMessage, BaseMessage
from langgraph.graph import END, StateGraph
from langgraph.prebuilt import ToolNode

from repolens.agent.state import AgentState
from repolens.agent.tools import AGENT_TOOLS
from repolens.config import get_settings

log = structlog.get_logger(__name__)


def build_agent_graph() -> Any:
    """Construct and compile the LangGraph agent.

    Returns a compiled StateGraph.
    """
    settings = get_settings()

    model = ChatAnthropic(
        model=settings.agent_model,
        api_key=settings.anthropic_api_key,
        max_tokens=settings.llm_max_tokens,
        temperature=settings.llm_temperature,
    ).bind_tools(AGENT_TOOLS)

    tool_node = ToolNode(AGENT_TOOLS)

    def call_model(state: AgentState) -> dict[str, object]:
        """Invoke the LLM with the current conversation."""
        response = model.invoke(state["messages"])
        return {
            "messages": [response],
            "step_count": state["step_count"] + 1,
        }

    def should_continue(state: AgentState) -> Literal["tools", "end"]:
        """Route: if the LLM wants to use a tool, go to tools; else finish."""
        s = get_settings()
        last: BaseMessage = state["messages"][-1]

        # Guard: max steps
        if state["step_count"] >= s.agent_max_steps:
            log.warning(
                "agent.max_steps_reached",
                steps=state["step_count"],
            )
            return "end"

        # If the LLM returned tool calls, route to tools
        if isinstance(last, AIMessage) and last.tool_calls:
            return "tools"

        return "end"

    # Build the graph
    graph: StateGraph[AgentState] = StateGraph(AgentState)
    graph.add_node("agent", call_model)
    graph.add_node("tools", tool_node)

    graph.set_entry_point("agent")
    graph.add_conditional_edges("agent", should_continue, {"tools": "tools", "end": END})
    graph.add_edge("tools", "agent")

    return graph.compile()
