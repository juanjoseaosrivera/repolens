"""Agent chat endpoint — LangGraph agent with streaming tool calls via SSE."""

import json
import time
from collections.abc import AsyncIterator
from typing import Any

import structlog
from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import StreamingResponse
from langchain_core.messages import HumanMessage, SystemMessage
from sqlalchemy.ext.asyncio import AsyncSession

from repolens.agent.graph import build_agent_graph
from repolens.agent.prompts import SYSTEM_PROMPT_V2
from repolens.api.deps import get_session
from repolens.api.schemas import ChatRequest
from repolens.storage.models import Repository

log = structlog.get_logger(__name__)

router = APIRouter(prefix="/agent", tags=["agent"])

_compiled_graph = None


def _get_graph() -> Any:
    global _compiled_graph
    if _compiled_graph is None:
        _compiled_graph = build_agent_graph()
    return _compiled_graph


@router.post("/chat")
async def agent_chat(
    body: ChatRequest,
    session: AsyncSession = Depends(get_session),
) -> StreamingResponse:
    """Run the LangGraph agent and stream tool calls + tokens via SSE."""
    repo = await session.get(Repository, body.repository_id)
    if repo is None:
        raise HTTPException(status_code=404, detail="Repository not found")
    if repo.status != "ready":
        raise HTTPException(
            status_code=409,
            detail=f"Repository is not ready (status: {repo.status})",
        )

    log.info(
        "agent_chat.request",
        repository_id=str(body.repository_id),
        question_len=len(body.question),
    )

    return StreamingResponse(
        _stream_agent(str(body.repository_id), body.question),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",
        },
    )


async def _stream_agent(
    repository_id: str,
    question: str,
) -> AsyncIterator[str]:
    """Run the agent graph and yield SSE events for each step."""
    graph = _get_graph()
    start_time = time.monotonic()

    initial_state = {
        "messages": [
            SystemMessage(content=SYSTEM_PROMPT_V2),
            HumanMessage(content=question),
        ],
        "repository_id": repository_id,
        "step_count": 0,
        "total_tokens": 0,
    }

    step = 0
    async for event in graph.astream_events(initial_state, version="v2"):
        kind = event["event"]

        if kind == "on_chat_model_stream":
            # Token streaming from the LLM
            chunk = event["data"]["chunk"]
            if hasattr(chunk, "content"):
                content = chunk.content
                # Anthropic returns content as a list of blocks; extract text
                if isinstance(content, list):
                    text = "".join(
                        block.get("text", "")
                        for block in content
                        if isinstance(block, dict) and block.get("type") == "text"
                    )
                elif isinstance(content, str):
                    text = content
                else:
                    text = ""
                if text:
                    yield _sse({"type": "token", "data": text})

        elif kind == "on_tool_start":
            # Tool invocation starting
            tool_name = event.get("name", "unknown")
            tool_input = event["data"].get("input", {})
            yield _sse(
                {
                    "type": "tool_call_start",
                    "data": {
                        "step": step,
                        "tool": tool_name,
                        "input": tool_input,
                    },
                }
            )

        elif kind == "on_tool_end":
            # Tool result
            tool_name = event.get("name", "unknown")
            output = event["data"].get("output", "")
            output_str = str(output) if not isinstance(output, str) else output
            # Truncate long tool outputs for the SSE stream
            if len(output_str) > 2000:
                output_str = output_str[:2000] + "... (truncated)"
            yield _sse(
                {
                    "type": "tool_call_result",
                    "data": {
                        "step": step,
                        "tool": tool_name,
                        "result": output_str,
                    },
                }
            )
            step += 1

    elapsed = time.monotonic() - start_time
    yield _sse(
        {
            "type": "metrics",
            "data": {"elapsed_seconds": round(elapsed, 2), "steps": step},
        }
    )
    yield "data: [DONE]\n\n"


def _sse(payload: dict[str, object]) -> str:
    return f"data: {json.dumps(payload)}\n\n"
