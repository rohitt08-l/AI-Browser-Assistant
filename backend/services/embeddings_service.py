"""Remote embeddings (replaces the local HuggingFace / PyTorch model).

Only used for Q&A over pages too large to send in full, and only when
EMBEDDINGS_PROVIDER is set. Vectors are L2-normalised so a dot product is the
cosine similarity.
"""

from __future__ import annotations

import numpy as np
from openai import AsyncAzureOpenAI, AsyncOpenAI, OpenAIError

from backend.core.config import Settings
from backend.core.errors import LLMError

_BATCH = 256


class EmbeddingsService:
    def __init__(self, settings: Settings):
        common = {"timeout": settings.llm_timeout_seconds, "max_retries": settings.llm_max_retries}
        if settings.embeddings_provider == "azure":
            self._client: AsyncOpenAI = AsyncAzureOpenAI(
                api_key=settings.azure_openai_api_key,
                azure_endpoint=settings.azure_openai_endpoint,
                api_version=settings.azure_openai_api_version,
                **common,
            )
            self._model = settings.azure_embeddings_deployment
        elif settings.embeddings_provider == "openai":
            self._client = AsyncOpenAI(
                api_key=settings.openai_api_key, base_url=settings.openai_base_url, **common
            )
            self._model = settings.openai_embeddings_model
        else:
            raise ValueError("EmbeddingsService requires EMBEDDINGS_PROVIDER=azure|openai")

    async def embed(self, texts: list[str]) -> np.ndarray:
        vectors: list[list[float]] = []
        try:
            for start in range(0, len(texts), _BATCH):
                response = await self._client.embeddings.create(
                    model=self._model, input=texts[start : start + _BATCH]
                )
                vectors.extend(item.embedding for item in response.data)
        except OpenAIError as exc:
            raise LLMError("The embeddings provider returned an error.") from exc
        matrix = np.asarray(vectors, dtype=np.float32)
        norms = np.linalg.norm(matrix, axis=1, keepdims=True)
        return matrix / np.maximum(norms, 1e-12)

    async def aclose(self) -> None:
        await self._client.close()
