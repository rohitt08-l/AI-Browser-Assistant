import os

# The app module validates settings on import; give it a dummy key.
os.environ.setdefault("GROQ_API_KEY", "test-key")

import pytest
from fastapi.testclient import TestClient

from backend.app import create_app
from backend.core.config import Settings
from backend.core.errors import LLMError


class FakeLLM:
    """Records calls and returns canned responses; streams word by word."""

    def __init__(self, reply: str = "Hello **world** from the page.", fail: bool = False):
        self.reply = reply
        self.fail = fail
        self.complete_calls: list[list[dict]] = []
        self.stream_calls: list[list[dict]] = []

    async def complete(self, messages, max_tokens=None):
        self.complete_calls.append(messages)
        if self.fail:
            raise LLMError("provider down")
        return "- condensed point"

    async def stream(self, messages):
        self.stream_calls.append(messages)
        if self.fail:
            raise LLMError("provider down")
        for word in self.reply.split(" "):
            yield word + " "

    async def aclose(self):
        pass


@pytest.fixture
def settings(tmp_path):
    return Settings(groq_api_key="test-key", files_dir=str(tmp_path), max_context_tokens=2_000)


@pytest.fixture
def fake_llm():
    return FakeLLM()


@pytest.fixture
def client(settings, fake_llm):
    with TestClient(create_app(settings, llm=fake_llm)) as c:
        yield c
