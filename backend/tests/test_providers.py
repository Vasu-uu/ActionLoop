import json
import threading
from http.server import BaseHTTPRequestHandler, HTTPServer
from types import SimpleNamespace

import pytest

from app.schemas import Extraction
from app.services.extract import call_with_retries
from app.services.llm import AnthropicProvider, LLMError, OpenAICompatProvider, build_provider
from app.config import Settings

REPLY = {"summary": {"bullets": ["b"], "paragraph": "p"}, "action_items": [
    {"title": "Do it", "owner": "Ann", "owner_confidence": "high", "evidence_quote": "I will do it", "priority": "low"}]}


@pytest.fixture()
def fake_openai():
    seen = {"bodies": [], "replies": [json.dumps(REPLY)]}

    class H(BaseHTTPRequestHandler):
        def do_POST(self):
            body = json.loads(self.rfile.read(int(self.headers["Content-Length"])))
            seen["bodies"].append((self.path, self.headers.get("Authorization"), body))
            status = seen.get("status", 200)
            payload = {"choices": [{"message": {"content": seen["replies"].pop(0) if seen["replies"] else "{}"}}]}
            self.send_response(status)
            self.send_header("Content-Type", "application/json")
            self.end_headers()
            self.wfile.write(json.dumps(payload).encode())

        def log_message(self, *a):
            pass

    srv = HTTPServer(("127.0.0.1", 0), H)
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    seen["url"] = f"http://127.0.0.1:{srv.server_port}/v1"
    yield seen
    srv.shutdown()


def test_openai_compatible_roundtrip_and_validation_retry(fake_openai):
    fake_openai["replies"] = ["oops not json", json.dumps(REPLY)]
    p = OpenAICompatProvider("openai", fake_openai["url"], "m", api_key="sk-test")
    out = call_with_retries(p, "sys", "user", Extraction)
    assert out.action_items[0].owner == "Ann"
    path, auth, body = fake_openai["bodies"][0]
    assert path.endswith("/chat/completions") and auth == "Bearer sk-test"
    assert body["response_format"] == {"type": "json_object"} and body["messages"][0]["role"] == "system"
    assert len(fake_openai["bodies"]) == 2  # one retry with the error fed back


def test_openai_errors_are_friendly(fake_openai):
    fake_openai["status"] = 401
    with pytest.raises(LLMError, match="rejected the API key"):
        OpenAICompatProvider("openai", fake_openai["url"], "m", "bad").complete("s", [{"role": "user", "content": "u"}])
    with pytest.raises(LLMError, match="Could not connect"):
        OpenAICompatProvider("ollama", "http://127.0.0.1:1/v1", "m").complete("s", [{"role": "user", "content": "u"}])


def test_anthropic_provider_uses_messages_api(monkeypatch):
    p = AnthropicProvider("sk-ant-test", "claude-opus-5-5")
    captured = {}

    def create(**kw):
        captured.update(kw)
        return SimpleNamespace(stop_reason="end_turn", content=[SimpleNamespace(type="text", text=json.dumps(REPLY))])

    monkeypatch.setattr(p.client.messages, "create", create)
    assert call_with_retries(p, "sys", "usr", Extraction).summary.bullets == ["b"]
    assert captured["model"] == "claude-opus-5-5" and captured["system"] == "sys"
    assert "temperature" not in captured  # sampling params are rejected by current models

    monkeypatch.setattr(p.client.messages, "create", lambda **kw: SimpleNamespace(stop_reason="refusal", content=[]))
    with pytest.raises(LLMError, match="declined"):
        p.complete("s", [{"role": "user", "content": "u"}])


def test_provider_selection_and_default_to_demo():
    assert build_provider(Settings(_env_file=None, llm_provider="", anthropic_api_key="", openai_api_key="")).name == "demo"
    assert build_provider(Settings(_env_file=None, llm_provider="", anthropic_api_key="k")).name == "anthropic"
    assert build_provider(Settings(_env_file=None, llm_provider="ollama")).local is True
    assert build_provider(Settings(_env_file=None, llm_provider="openai", openai_api_key="k")).local is False
    # misconfigured explicit choice (no key) degrades to demo instead of crashing
    assert build_provider(Settings(_env_file=None, llm_provider="anthropic", anthropic_api_key="")).name == "demo"
