"""Chat / Q&A endpoint — retrieve-then-generate with SSE streaming."""

import json
from collections.abc import AsyncIterator

import structlog
from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import StreamingResponse
from sqlalchemy.ext.asyncio import AsyncSession

from repolens.agent.prompts import SYSTEM_PROMPT_V1
from repolens.api.deps import get_completion_client, get_embedding_client, get_session
from repolens.api.schemas import ChatRequest
from repolens.llm import CompletionClient, EmbeddingClient
from repolens.retrieval.vector import semantic_search
from repolens.storage.models import Repository

log = structlog.get_logger(__name__)

router = APIRouter(prefix="/chat", tags=["chat"])


@router.post("")
async def chat(
    body: ChatRequest,
    session: AsyncSession = Depends(get_session),
    completion_client: CompletionClient = Depends(get_completion_client),
    embedding_client: EmbeddingClient = Depends(get_embedding_client),
) -> StreamingResponse:
    """Answer a question about a repository via streamed SSE."""
    # Validate repository exists and is ready
    repo = await session.get(Repository, body.repository_id)
    if repo is None:
        raise HTTPException(status_code=404, detail="Repository not found")
    if repo.status != "ready":
        raise HTTPException(
            status_code=409,
            detail=f"Repository is not ready (status: {repo.status})",
        )

    # Retrieve relevant chunks
    chunks = await semantic_search(
        body.question,
        body.repository_id,
        session,
        embedder=embedding_client,
    )

    if not chunks:
        raise HTTPException(
            status_code=404,
            detail="No relevant code found. The repository may not have been ingested yet.",
        )

    # Build context string from retrieved chunks
    context_parts: list[str] = []
    sources_payload: list[dict[str, object]] = []
    for i, chunk in enumerate(chunks, 1):
        context_parts.append(
            f"### Chunk {i}: `{chunk.file_path}:{chunk.start_line}-{chunk.end_line}`\n"
            f"```{chunk.language or ''}\n{chunk.content}\n```"
        )
        sources_payload.append(
            {
                "file_path": chunk.file_path,
                "start_line": chunk.start_line,
                "end_line": chunk.end_line,
                "score": round(chunk.score, 4),
            }
        )

    context = "\n\n".join(context_parts)
    system_prompt = SYSTEM_PROMPT_V1.format(context=context)

    messages = [{"role": "user", "content": body.question}]

    log.info(
        "chat.request",
        repository_id=str(body.repository_id),
        question_len=len(body.question),
        context_chunks=len(chunks),
    )

    return StreamingResponse(
        _stream_response(completion_client, system_prompt, messages, sources_payload),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",
        },
    )


async def _stream_response(
    client: CompletionClient,
    system: str,
    messages: list[dict[str, str]],
    sources: list[dict[str, object]],
) -> AsyncIterator[str]:
    """Yield SSE events: sources metadata, streamed tokens, then [DONE]."""
    # First event: sources metadata
    yield f"data: {json.dumps({'type': 'sources', 'data': sources})}\n\n"

    # Stream tokens
    async for token in client.stream(system=system, messages=messages):
        yield f"data: {json.dumps({'type': 'token', 'data': token})}\n\n"

    # Done signal
    yield "data: [DONE]\n\n"
