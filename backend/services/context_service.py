"""Decide what part of a page the model gets to see.

Strategy (replaces the old per-request FAISS index over the first 10k chars):

* Small pages (the vast majority) are sent to the model **in full**. This is
  faster, cheaper and more accurate than retrieval.
* Large pages are split into chunks.
  - Q&A retrieves the most relevant chunks until the token budget is filled,
    using embeddings when configured or BM25 otherwise.
  - Summaries / notes / documents use map-reduce over **all** chunks
    (see `pipeline.py`) so nothing on the page is skipped.
"""

from __future__ import annotations

import hashlib
import math
import re
from collections import Counter, OrderedDict

import numpy as np

from backend.services.embeddings_service import EmbeddingsService

_WORD_RE = re.compile(r"[a-z0-9]+")
_STOPWORDS = frozenset(
    "a an and are as at be by for from has have how i in is it its of on or that the this to was "
    "what when where which who why will with you your does do did can could should would about".split()
)


def estimate_tokens(text: str) -> int:
    """Cheap token estimate (~4 chars/token for English) — good enough for budgeting."""
    return math.ceil(len(text) / 4)


def normalise_whitespace(text: str) -> str:
    text = re.sub(r"[ \t ]+", " ", text)
    text = re.sub(r"\n\s*\n\s*", "\n\n", text)
    return text.strip()


def split_text(text: str, chunk_size: int, overlap: int) -> list[str]:
    """Split on paragraph, then sentence, then word boundaries."""
    separators = ["\n\n", "\n", ". ", " "]

    def _split(segment: str, level: int) -> list[str]:
        if len(segment) <= chunk_size or level >= len(separators):
            return [segment[i : i + chunk_size] for i in range(0, len(segment), chunk_size)] or [""]
        sep = separators[level]
        parts = segment.split(sep)
        out: list[str] = []
        current = ""
        for part in parts:
            piece = part if not current else current + sep + part
            if len(piece) <= chunk_size:
                current = piece
                continue
            if current:
                out.append(current)
            if len(part) > chunk_size:
                out.extend(_split(part, level + 1))
                current = ""
            else:
                current = part
        if current:
            out.append(current)
        return out

    chunks = [c.strip() for c in _split(text, 0) if c.strip()]
    if overlap <= 0 or len(chunks) < 2:
        return chunks
    # Prepend the tail of the previous chunk so ideas spanning a boundary survive.
    with_overlap = [chunks[0]]
    for prev, cur in zip(chunks, chunks[1:]):
        tail = prev[-overlap:]
        cut = tail.find(" ")
        tail = tail[cut + 1 :] if cut != -1 else tail
        with_overlap.append(f"{tail} {cur}")
    return with_overlap


def group_chunks(chunks: list[str], max_tokens: int) -> list[str]:
    """Pack consecutive chunks into sections that each fit `max_tokens` (for map-reduce)."""
    sections: list[str] = []
    current: list[str] = []
    size = 0
    for chunk in chunks:
        tokens = estimate_tokens(chunk)
        if current and size + tokens > max_tokens:
            sections.append("\n\n".join(current))
            current, size = [], 0
        current.append(chunk)
        size += tokens
    if current:
        sections.append("\n\n".join(current))
    return sections


def _tokenize(text: str) -> list[str]:
    return [w for w in _WORD_RE.findall(text.lower()) if w not in _STOPWORDS]


def bm25_scores(chunks: list[str], query: str, k1: float = 1.5, b: float = 0.75) -> list[float]:
    docs = [_tokenize(c) for c in chunks]
    terms = set(_tokenize(query))
    if not terms or not docs:
        return [0.0] * len(chunks)
    avg_len = sum(len(d) for d in docs) / len(docs) or 1.0
    df = Counter(t for d in docs for t in set(d) if t in terms)
    n = len(docs)
    scores = []
    for doc in docs:
        tf = Counter(doc)
        score = 0.0
        for t in terms:
            if not tf[t]:
                continue
            idf = math.log(1 + (n - df[t] + 0.5) / (df[t] + 0.5))
            score += idf * tf[t] * (k1 + 1) / (tf[t] + k1 * (1 - b + b * len(doc) / avg_len))
        scores.append(score)
    return scores


class ContextService:
    def __init__(
        self,
        embeddings: EmbeddingsService | None,
        chunk_size: int,
        chunk_overlap: int,
        cache_size: int = 64,
    ):
        self._embeddings = embeddings
        self._chunk_size = chunk_size
        self._chunk_overlap = chunk_overlap
        self._cache_size = cache_size
        # content-hash -> (chunks, chunk embeddings or None); LRU-evicted.
        self._cache: OrderedDict[str, tuple[list[str], np.ndarray | None]] = OrderedDict()

    def chunks(self, text: str) -> list[str]:
        return self._entry(text)[0]

    def _entry(self, text: str) -> tuple[list[str], np.ndarray | None]:
        key = hashlib.sha256(text.encode()).hexdigest()
        if key in self._cache:
            self._cache.move_to_end(key)
            return self._cache[key]
        entry = (split_text(text, self._chunk_size, self._chunk_overlap), None)
        self._remember(key, entry)
        return entry

    def _remember(self, key: str, entry: tuple[list[str], np.ndarray | None]) -> None:
        self._cache[key] = entry
        self._cache.move_to_end(key)
        while len(self._cache) > self._cache_size:
            self._cache.popitem(last=False)

    async def retrieve(self, text: str, query: str, max_tokens: int) -> str:
        """Return the most relevant chunks (in page order) that fit in `max_tokens`."""
        chunks, vectors = self._entry(text)
        scores: list[float]
        if self._embeddings is not None:
            key = hashlib.sha256(text.encode()).hexdigest()
            if vectors is None:
                vectors = await self._embeddings.embed(chunks)
                self._remember(key, (chunks, vectors))
            query_vec = (await self._embeddings.embed([query]))[0]
            scores = (vectors @ query_vec).tolist()
        else:
            scores = bm25_scores(chunks, query)

        ranked = sorted(range(len(chunks)), key=lambda i: scores[i], reverse=True)
        chosen: list[int] = []
        used = 0
        for i in ranked:
            cost = estimate_tokens(chunks[i])
            if used + cost > max_tokens:
                continue
            chosen.append(i)
            used += cost
        # Always include the opening chunk: it usually carries the title / lede.
        if 0 not in chosen and chunks and used + estimate_tokens(chunks[0]) <= max_tokens:
            chosen.append(0)
        return "\n\n[...]\n\n".join(chunks[i] for i in sorted(chosen))
