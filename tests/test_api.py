import json

from fastapi.testclient import TestClient

from backend.app import create_app
from tests.conftest import FakeLLM

PAGE = "Photosynthesis converts light energy into chemical energy in plants."


def sse_events(response):
    return [json.loads(line[6:]) for line in response.text.splitlines() if line.startswith("data: ")]


def test_health(client):
    assert client.get("/health").json()["status"] == "ok"


def test_root_describes_service(client):
    body = client.get("/").json()
    assert body["status"] == "ok" and body["docs"] == "/docs"


def test_ask_qa_sends_full_page(client, fake_llm):
    r = client.post("/ask", json={"question": "What does it convert?", "page_content": PAGE, "task_type": "QA"})
    assert r.status_code == 200
    body = r.json()
    assert body["task"] == "qa"
    assert body["answer"].startswith("Hello")
    prompt = fake_llm.stream_calls[0][-1]["content"]
    assert "<page>" in prompt and PAGE in prompt


def test_summary_of_small_page_uses_whole_page(client, fake_llm):
    r = client.post("/ask", json={"page_content": PAGE, "task_type": "summarize"})
    assert r.status_code == 200
    assert PAGE in fake_llm.stream_calls[0][-1]["content"]
    assert fake_llm.complete_calls == []  # no extra classifier / map calls


def test_auto_routes_without_llm_call(client, fake_llm):
    r = client.post("/ask", json={"question": "Give me a quick summary", "page_content": PAGE})
    assert r.json()["task"] == "summarize"
    assert fake_llm.complete_calls == []


def test_invalid_task_is_422(client):
    r = client.post("/ask", json={"question": "x", "page_content": PAGE, "task_type": "dance"})
    assert r.status_code == 422


def test_question_required_for_qa(client):
    assert client.post("/ask", json={"page_content": PAGE, "task_type": "qa"}).status_code == 422


def test_page_too_large_is_413(settings, fake_llm):
    settings.max_page_chars = 1_000
    with TestClient(create_app(settings, llm=fake_llm)) as c:
        r = c.post("/ask/stream", json={"question": "q", "page_content": "x" * 1_001})
    assert r.status_code == 413


def test_llm_failure_is_502(settings):
    with TestClient(create_app(settings, llm=FakeLLM(fail=True))) as c:
        r = c.post("/ask", json={"question": "q?", "page_content": PAGE, "task_type": "qa"})
    assert r.status_code == 502
    assert "provider down" in r.json()["detail"]


def test_stream_events(client):
    r = client.post("/ask/stream", json={"question": "What?", "page_content": PAGE, "task_type": "qa"})
    assert r.headers["content-type"].startswith("text/event-stream")
    events = sse_events(r)
    assert events[0] == {"type": "meta", "task": "qa"}
    assert "".join(e["content"] for e in events if e["type"] == "token").startswith("Hello")
    assert events[-1] == {"type": "done", "file_url": None}


def test_stream_error_event(settings):
    with TestClient(create_app(settings, llm=FakeLLM(fail=True))) as c:
        events = sse_events(c.post("/ask/stream", json={"question": "q?", "page_content": PAGE, "task_type": "qa"}))
    assert events[-1]["type"] == "error"


def test_generate_doc_returns_downloadable_pdf(settings):
    llm = FakeLLM(reply="# Report\n\n## Overview\n\nUses <tags> & ampersands safely.\n\n- point one\n- point two")
    with TestClient(create_app(settings, llm=llm)) as c:
        body = c.post("/ask", json={"page_content": PAGE, "task_type": "generate_doc"}).json()
        assert body["file_url"]
        pdf = c.get(body["file_url"])
    assert pdf.status_code == 200
    assert pdf.content.startswith(b"%PDF")
    assert "attachment" in pdf.headers["content-disposition"]


def test_file_download_rejects_bad_ids(client):
    assert client.get("/files/..%2F..%2Fetc%2Fpasswd").status_code == 404
    assert client.get("/files/" + "0" * 32).status_code == 404


def test_long_page_summary_uses_map_reduce(client, fake_llm):
    long_page = "\n\n".join(f"Paragraph {i} about topic {i}. " * 20 for i in range(200))
    events = sse_events(client.post("/ask/stream", json={"page_content": long_page, "task_type": "notes"}))
    assert any(e["type"] == "status" for e in events)
    assert len(fake_llm.complete_calls) > 1  # every section was condensed
    final_prompt = fake_llm.stream_calls[0][-1]["content"]
    assert "condensed point" in final_prompt


def test_long_page_qa_retrieves_relevant_chunk(client, fake_llm):
    filler = "\n\n".join(f"Unrelated filler sentence number {i} about cooking pasta." * 10 for i in range(150))
    page = filler + "\n\nThe secret launch code is ZEBRA-42 and it was set in 1999.\n\n" + filler
    client.post("/ask", json={"question": "What is the secret launch code?", "page_content": page, "task_type": "qa"})
    prompt = fake_llm.stream_calls[0][-1]["content"]
    assert "ZEBRA-42" in prompt
    assert len(prompt) < len(page)


def test_history_is_forwarded(client, fake_llm):
    history = [{"role": "user", "content": "first q"}, {"role": "assistant", "content": "first a"}]
    client.post("/ask", json={"question": "and then?", "page_content": PAGE, "task_type": "qa", "history": history})
    roles = [m["role"] for m in fake_llm.stream_calls[0]]
    assert roles == ["system", "user", "assistant", "user"]


def test_whitespace_only_page_is_422(client):
    assert client.post("/ask", json={"page_content": "   \n ", "task_type": "summarize"}).status_code == 422
