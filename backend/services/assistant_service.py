"""Orchestrates a request: route the task, build context, stream the answer.

`run()` is an async generator of events, consumed by both the streaming
(SSE) and the plain JSON endpoints:

    {"type": "meta",   "task": "summarize"}
    {"type": "status", "message": "Reading a long page (3 sections)..."}
    {"type": "token",  "content": "..."}
    {"type": "done",   "file_id": "..." | None}
"""

from __future__ import annotations

import asyncio
import logging
from collections.abc import AsyncIterator
from typing import Any

from backend.core.config import Settings
from backend.core.errors import PayloadTooLargeError
from backend.models.schemas import AskRequest, TaskType
from backend.services import prompts
from backend.services.context_service import (
    ContextService,
    estimate_tokens,
    group_chunks,
    normalise_whitespace,
)
from backend.services.file_store import FileStore
from backend.services.llm_service import LLMService, Message
from backend.services.pdf_service import markdown_to_pdf
from backend.services.router_service import classify_task

logger = logging.getLogger(__name__)

Event = dict[str, Any]

# Tokens kept free for the system prompt, task instructions and the answer.
_PROMPT_OVERHEAD_TOKENS = 1_500
_MAX_REDUCE_ROUNDS = 3


class AssistantService:
    def __init__(self, settings: Settings, llm: LLMService, context: ContextService, files: FileStore):
        self._settings = settings
        self._llm = llm
        self._context = context
        self._files = files

    def validate(self, req: AskRequest) -> None:
        if len(req.page_content) > self._settings.max_page_chars:
            raise PayloadTooLargeError(
                f"Page content is too large ({len(req.page_content):,} characters; "
                f"limit is {self._settings.max_page_chars:,})."
            )

    async def run(self, req: AskRequest) -> AsyncIterator[Event]:
        self.validate(req)
        task = req.task_type
        if task == TaskType.AUTO:
            task = await classify_task(req.question, self._llm)
        yield {"type": "meta", "task": task.value}

        history = self._history(req)
        budget = self._page_budget(req, history)
        content = normalise_whitespace(req.page_content)

        if estimate_tokens(content) <= budget:
            page = prompts.page_block(content, req.page_title, req.page_url)
        elif task == TaskType.QA:
            query = f"{req.question}\n{req.selection}".strip()
            excerpts = await self._context.retrieve(content, query, budget)
            page = prompts.page_block(excerpts, req.page_title, req.page_url, partial=True)
        else:
            sections = group_chunks(self._context.chunks(content), budget)
            yield {"type": "status", "message": f"Reading a long page ({len(sections)} sections)..."}
            condensed = await self._map_reduce(sections, req.page_title, budget)
            page = prompts.page_block(
                "Condensed notes covering the whole page, section by section:\n\n" + condensed,
                req.page_title,
                req.page_url,
            )

        messages: list[Message] = [
            {"role": "system", "content": prompts.SYSTEM_PROMPT},
            *history,
            {"role": "user", "content": prompts.user_turn(task, page, req.question, req.selection)},
        ]

        answer: list[str] = []
        async for token in self._llm.stream(messages):
            answer.append(token)
            yield {"type": "token", "content": token}

        file_id = None
        if task == TaskType.GENERATE_DOC:
            pdf = await asyncio.to_thread(markdown_to_pdf, "".join(answer), req.page_title or "Generated Document")
            file_id = self._files.save(pdf)
        yield {"type": "done", "file_id": file_id}

    def _history(self, req: AskRequest) -> list[Message]:
        limit = self._settings.max_history_messages
        recent = req.history[-limit:] if limit else []
        return [{"role": m.role, "content": m.content} for m in recent]

    def _page_budget(self, req: AskRequest, history: list[Message]) -> int:
        used = (
            _PROMPT_OVERHEAD_TOKENS
            + estimate_tokens(req.question)
            + estimate_tokens(req.selection)
            + sum(estimate_tokens(m["content"]) for m in history)
        )
        return max(self._settings.max_context_tokens - used, 500)

    async def _map_reduce(self, sections: list[str], title: str, budget: int) -> str:
        """Condense every section of a long page into notes until they fit `budget`."""
        semaphore = asyncio.Semaphore(self._settings.max_map_concurrency)

        async def condense(section: str) -> str:
            async with semaphore:
                return await self._llm.complete(
                    [
                        {"role": "system", "content": prompts.SYSTEM_PROMPT},
                        {
                            "role": "user",
                            "content": f"{prompts.page_block(section, title)}\n\nTask: {prompts.MAP_INSTRUCTION}",
                        },
                    ]
                )

        for _ in range(_MAX_REDUCE_ROUNDS):
            notes = await asyncio.gather(*(condense(s) for s in sections))
            combined = "\n\n".join(f"### Part {i}\n{n.strip()}" for i, n in enumerate(notes, 1))
            if estimate_tokens(combined) <= budget:
                return combined
            sections = group_chunks(combined.split("\n\n"), budget)
        # Still too long after several rounds: keep what fits rather than failing.
        return combined[: budget * 4]
