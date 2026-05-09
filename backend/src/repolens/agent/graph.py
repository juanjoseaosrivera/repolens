"""LangGraph agent — cyclic state machine with search_code, query_graph, read_file tools.

The agent decides which tool to use (or to answer directly), executes it,
and loops until it has enough context or hits a guard limit.
"""

import copy
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

    # The LLM sees tools *without* the injected repository_id arg
    model = ChatAnthropic(
        model=settings.agent_model,
        api_key=settings.anthropic_api_key,
        max_tokens=settings.llm_max_tokens,
        temperature=settings.llm_temperature,
    ).bind_tools(AGENT_TOOLS)

    # The ToolNode executes with the full signature (including injected args)
    tool_node = ToolNode(AGENT_TOOLS)

    def inject_repo_id(state: AgentState) -> dict[str, object]:
        """Inject repository_id into tool call args before the ToolNode runs."""
        last: BaseMessage = state["messages"][-1]
        if not isinstance(last, AIMessage) or not last.tool_calls:
            return {"messages": []}

        repo_id = state["repository_id"]
        patched = copy.deepcopy(last)
        for tc in patched.tool_calls:
            tc["args"]["repository_id"] = repo_id
        return {"messages": [patched]}

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
    graph.add_node("inject_repo_id", inject_repo_id)
    graph.add_node("tools", tool_node)

    graph.set_entry_point("agent")
    graph.add_conditional_edges("agent", should_continue, {"tools": "inject_repo_id", "end": END})
    graph.add_edge("inject_repo_id", "tools")
    graph.add_edge("tools", "agent")

    return graph.compile()
