"""LangGraph agent state definition."""

from typing import Annotated

from langchain_core.messages import BaseMessage
from langgraph.graph.message import add_messages
from typing_extensions import TypedDict


class AgentState(TypedDict):
    """Typed state for the RepoLens agent graph.

    Attributes:
        messages: Conversation history (LangChain message objects).
        repository_id: UUID of the repository being queried.
        step_count: Number of tool-use cycles completed.
        total_tokens: Running estimate of tokens consumed.
    """

    messages: Annotated[list[BaseMessage], add_messages]
    repository_id: str
    step_count: int
    total_tokens: int
