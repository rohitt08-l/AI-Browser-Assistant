import pytest
from openai import APIConnectionError

from backend.core.config import Settings
from backend.core.errors import LLMError
from backend.models.schemas import AskRequest, TaskType
from backend.services.context_service import bm25_scores, group_chunks, split_text
from backend.services.llm_service import LLMService
from backend.services.pdf_service import markdown_to_pdf
from backend.services.router_service import classify_by_rules, classify_task, parse_label


@pytest.mark.parametrize("raw", ["QA", " qa ", "Qa"])
def test_task_normalisation(raw):
    assert AskRequest(question="q", page_content="p", task_type=raw).task_type == TaskType.QA


def test_task_normalisation_generate_doc():
    assert AskRequest(page_content="p", task_type="Generate-Doc").task_type == TaskType.GENERATE_DOC


@pytest.mark.parametrize(
    "question,expected",
    [
        ("summarize this", [TaskType.SUMMARIZE]),
        ("tl;dr please", [TaskType.SUMMARIZE]),
        ("make study notes", [TaskType.NOTES]),
        ("export this as a PDF", [TaskType.GENERATE_DOC]),
        ("create a report on this", [TaskType.GENERATE_DOC]),
        ("what does this document say about taxes?", []),
        ("who wrote this?", []),
    ],
)
def test_rules(question, expected):
    assert classify_by_rules(question) == expected


@pytest.mark.parametrize(
    "reply,expected",
    [
        ("QA.", TaskType.QA),
        ("summarize", TaskType.SUMMARIZE),
        ("Generate_Doc", TaskType.GENERATE_DOC),
        ("notes", TaskType.NOTES),
        ("banana", TaskType.QA),
    ],
)
def test_parse_label(reply, expected):
    assert parse_label(reply) == expected


async def test_ambiguous_question_asks_llm():
    class LLM:
        async def complete(self, messages, max_tokens=None):
            return "NOTES."

    assert await classify_task("summarize this into notes", LLM()) == TaskType.NOTES


def test_split_text_respects_size_and_covers_text():
    text = " ".join(f"word{i}" for i in range(3000))
    chunks = split_text(text, chunk_size=500, overlap=50)
    assert all(len(c) <= 560 for c in chunks)
    assert "word0" in chunks[0] and "word2999" in chunks[-1]


def test_group_chunks():
    assert len(group_chunks(["a" * 400] * 10, max_tokens=250)) == 5


def test_bm25_prefers_relevant_chunk():
    scores = bm25_scores(["cats purr softly", "the stock market fell", "dogs bark"], "why did the market fall")
    assert scores.index(max(scores)) == 1


def test_pdf_handles_markup_characters():
    pdf = markdown_to_pdf("# T\n\nA < B && C > D <script>\n\n1. one\n2. two\n\n- **bold** *it* `code`")
    assert pdf.startswith(b"%PDF")


def test_settings_fail_fast_without_key():
    with pytest.raises(ValueError, match="AZURE_OPENAI_API_KEY"):
        Settings(_env_file=None, llm_provider="azure", groq_api_key=None)


class _FakeCompletions:
    def __init__(self, fail):
        self.fail = fail

    async def create(self, **kwargs):
        if self.fail:
            raise APIConnectionError(request=None)

        class R:
            choices = [type("C", (), {"message": type("M", (), {"content": "from fallback"})()})()]

        return R()


def _client(fail):
    return type("Client", (), {"chat": type("Chat", (), {"completions": _FakeCompletions(fail)})()})()


async def test_fallback_provider_used_when_primary_fails():
    settings = Settings(_env_file=None, groq_api_key="k", openai_api_key="k", llm_fallback_provider="openai")
    svc = LLMService(settings)
    svc._backends[0].client = _client(fail=True)
    svc._backends[1].client = _client(fail=False)
    assert await svc.complete([{"role": "user", "content": "hi"}]) == "from fallback"


async def test_all_providers_failing_raises_llm_error():
    svc = LLMService(Settings(_env_file=None, groq_api_key="k"))
    svc._backends[0].client = _client(fail=True)
    with pytest.raises(LLMError):
        await svc.complete([{"role": "user", "content": "hi"}])
