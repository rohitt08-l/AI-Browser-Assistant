"""Decide which task an 'auto' request maps to.

Keyword rules resolve almost every request instantly with no LLM call. The
model is consulted only when the rules are ambiguous, and its answer is
parsed defensively (it may reply "QA." or "summarize") with QA as the safe
default.
"""

from __future__ import annotations

import logging
import re

from backend.core.errors import LLMError
from backend.models.schemas import TaskType
from backend.services.llm_service import LLMService
from backend.services.prompts import CLASSIFY_PROMPT

logger = logging.getLogger(__name__)

_RULES: dict[TaskType, re.Pattern[str]] = {
    TaskType.GENERATE_DOC: re.compile(
        # "pdf" alone, or a creation verb near doc/report ("what does this document say" stays QA).
        r"\bpdf\b|\b(generate|create|make|write|export|draft|prepare|produce|give me)\b.{0,40}"
        r"\b(docx?|document|report|write[- ]?up)\b",
        re.I,
    ),
    TaskType.NOTES: re.compile(
        r"\b(notes?|key points?|bullet(ed)? points?|outline|study (guide|material)|cheat ?sheet|flashcards?)\b",
        re.I,
    ),
    TaskType.SUMMARIZE: re.compile(
        r"\b(summar(y|ise|ize|ized|ised)|tl;?dr|overview|gist|recap|in short|what is this (page|article) about)\b",
        re.I,
    ),
}

_LABELS = {
    "GENERATE_DOC": TaskType.GENERATE_DOC,
    "SUMMARIZE": TaskType.SUMMARIZE,
    "NOTES": TaskType.NOTES,
    "QA": TaskType.QA,
}


def classify_by_rules(question: str) -> list[TaskType]:
    return [task for task, pattern in _RULES.items() if pattern.search(question)]


def parse_label(text: str) -> TaskType:
    upper = text.upper().replace("-", "_").replace(" ", "_")
    for label, task in _LABELS.items():  # GENERATE_DOC checked first on purpose
        if label in upper:
            return task
    if "SUMMAR" in upper:
        return TaskType.SUMMARIZE
    return TaskType.QA


async def classify_task(question: str, llm: LLMService) -> TaskType:
    matches = classify_by_rules(question)
    if len(matches) == 1:
        return matches[0]
    if not matches:
        return TaskType.QA
    try:
        reply = await llm.complete(
            [{"role": "user", "content": CLASSIFY_PROMPT.format(question=question)}], max_tokens=5
        )
    except LLMError:
        logger.warning("Classifier call failed; using first rule match")
        return matches[0]
    return parse_label(reply)
