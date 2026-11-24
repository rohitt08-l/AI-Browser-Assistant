"""Ask endpoints: streaming (SSE) and plain JSON."""

from __future__ import annotations

import json
import logging
from collections.abc import AsyncIterator

from fastapi import APIRouter, Request
from fastapi.responses import StreamingResponse

from backend.core.errors import AppError
from backend.models.schemas import AskRequest, AskResponse, TaskType
from backend.services.assistant_service import AssistantService

logger = logging.getLogger(__name__)
router = APIRouter(tags=["assistant"])


def _service(request: Request) -> AssistantService:
    return request.app.state.assistant


def _file_url(request: Request, file_id: str | None) -> str | None:
    return str(request.url_for("download_file", file_id=file_id)) if file_id else None


@router.post("/ask", response_model=AskResponse)
async def ask(data: AskRequest, request: Request) -> AskResponse:
    """Non-streaming endpoint: returns the complete answer as JSON."""
    task = data.task_type
    parts: list[str] = []
    file_id = None
    async for event in _service(request).run(data):
        if event["type"] == "meta":
            task = TaskType(event["task"])
        elif event["type"] == "token":
            parts.append(event["content"])
        elif event["type"] == "done":
            file_id = event["file_id"]
    return AskResponse(answer="".join(parts), task=task, file_url=_file_url(request, file_id))


@router.post("/ask/stream")
async def ask_stream(data: AskRequest, request: Request) -> StreamingResponse:
    """Server-Sent Events stream of `meta`, `status`, `token`, `done` and `error` events."""
    service = _service(request)
    service.validate(data)  # fail with a proper HTTP status before the stream starts

    async def events() -> AsyncIterator[str]:
        try:
            async for event in service.run(data):
                if event["type"] == "done":
                    event = {"type": "done", "file_url": _file_url(request, event["file_id"])}
                yield f"data: {json.dumps(event)}\n\n"
        except AppError as exc:
            yield f"data: {json.dumps({'type': 'error', 'message': exc.message})}\n\n"
        except Exception:  # never leak internals into the stream
            logger.exception("Unexpected error while streaming")
            yield f"data: {json.dumps({'type': 'error', 'message': 'Unexpected server error.'})}\n\n"

    return StreamingResponse(
        events(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )
