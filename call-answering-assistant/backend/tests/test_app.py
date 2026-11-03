from __future__ import annotations

import dataclasses
from types import SimpleNamespace

import pytest
from fastapi.testclient import TestClient
from twilio.request_validator import RequestValidator

from app.agent import ClaudeAssistant, _to_messages
from app.config import get_settings
from app.db import Database
from app.main import create_app

TOKEN = "test-app-token"
AUTH = {"Authorization": f"Bearer {TOKEN}"}


class FakeAssistant:
    def __init__(self) -> None:
        self.replies = [("Thanks Sam. Is this number the best one to reach you?", False),
                        ("Got it, I'll pass that on. Goodbye!", True)]

    def greeting(self, settings):
        return f"Hi, you've reached {settings['owner_name']}'s assistant."

    def reply(self, settings, caller, transcript):
        return self.replies.pop(0)

    def summarize(self, caller, transcript):
        return {"caller_name": "Sam", "callback_number": caller, "reason": "Dinner plans",
                "urgency": "normal", "summary": "Sam wants to confirm dinner Friday."}


class FakePush:
    def __init__(self) -> None:
        self.sent: list[dict] = []

    def notify_call(self, call):
        self.sent.append(call)


def make_settings(**overrides):
    base = dataclasses.replace(
        get_settings(), app_api_token=TOKEN, twilio_auth_token="twilio-secret",
        public_base_url="https://calls.example.com", validate_twilio_signature=False,
    )
    return dataclasses.replace(base, **overrides)


@pytest.fixture
def env(tmp_path):
    db = Database(str(tmp_path / "calls.db"))
    db.save_settings({"owner_name": "Abhinav"})
    push = FakePush()
    app = create_app(make_settings(), db=db, assistant=FakeAssistant(), push=push)
    return TestClient(app), db, push


def test_full_call_flow(env):
    client, db, push = env
    call = {"CallSid": "CA1", "From": "+15551234567", "To": "+15550000000"}

    r = client.post("/twilio/voice", data=call)
    assert r.status_code == 200
    assert "<Gather" in r.text and "Abhinav's assistant" in r.text

    r = client.post("/twilio/turn", data={**call, "SpeechResult": "It's Sam about dinner"})
    assert "best one to reach you" in r.text and "<Gather" in r.text

    r = client.post("/twilio/turn", data={**call, "SpeechResult": "Yes that's right, bye"})
    assert "<Hangup" in r.text

    r = client.post("/twilio/status", data={**call, "CallStatus": "completed"})
    assert r.status_code == 204

    stored = client.get("/api/calls/CA1", headers=AUTH).json()
    assert stored["status"] == "completed"
    assert stored["caller_name"] == "Sam"
    assert [t["role"] for t in stored["transcript"]] == [
        "assistant", "caller", "assistant", "caller", "assistant"]
    assert len(push.sent) == 1

    # A repeated status callback must not summarize or notify twice.
    client.post("/twilio/status", data={**call, "CallStatus": "completed"})
    assert len(push.sent) == 1


def test_silence_ends_call(env):
    client, _, _ = env
    call = {"CallSid": "CA2", "From": "+15551112222"}
    client.post("/twilio/voice", data=call)
    assert "still there" in client.post("/twilio/turn", data=call).text
    assert "<Hangup" in client.post("/twilio/turn", data=call).text


def test_api_requires_token(env):
    client, _, _ = env
    assert client.get("/api/calls").status_code == 401
    assert client.get("/api/calls", headers={"Authorization": "Bearer nope"}).status_code == 401
    assert client.get("/api/calls", headers=AUTH).json() == []


def test_settings_mark_read_delete(env):
    client, db, _ = env
    r = client.put("/api/settings", headers=AUTH, json={"instructions": "Say I'm at work until 6."})
    assert r.json()["instructions"] == "Say I'm at work until 6."
    assert r.json()["owner_name"] == "Abhinav"

    db.create_call("CA3", "+1555", "+1666")
    assert client.patch("/api/calls/CA3", headers=AUTH, json={"is_read": True}).json()["is_read"]
    assert client.delete("/api/calls/CA3", headers=AUTH).status_code == 204
    assert client.get("/api/calls/CA3", headers=AUTH).status_code == 404

    assert client.post("/api/devices", headers=AUTH, json={"token": "ABCDEF0123456789"}).status_code == 204
    assert db.device_tokens() == ["abcdef0123456789"]


def test_twilio_signature_enforced(tmp_path):
    settings = make_settings(validate_twilio_signature=True)
    app = create_app(settings, db=Database(str(tmp_path / "c.db")),
                     assistant=FakeAssistant(), push=FakePush())
    client = TestClient(app)
    data = {"CallSid": "CA9", "From": "+1555"}

    assert client.post("/twilio/voice", data=data).status_code == 403

    sig = RequestValidator("twilio-secret").compute_signature(
        "https://calls.example.com/twilio/voice", data)
    r = client.post("/twilio/voice", data=data, headers={"X-Twilio-Signature": sig})
    assert r.status_code == 200


def test_messages_start_with_user_and_alternate():
    msgs = _to_messages([
        {"role": "assistant", "text": "Hello"},
        {"role": "caller", "text": "Hi"},
        {"role": "caller", "text": "it's Sam"},
    ])
    assert [m["role"] for m in msgs] == ["user", "assistant", "user"]
    assert msgs[2]["content"] == "Hi it's Sam"


def test_reply_strips_end_marker_and_handles_refusal():
    def fake_create(**kwargs):
        assert kwargs["fallbacks"] == "default"
        return fake_create.response

    client = SimpleNamespace(beta=SimpleNamespace(messages=SimpleNamespace(create=fake_create)))
    bot = ClaudeAssistant("claude-opus-5-5", client=client)
    transcript = [{"role": "assistant", "text": "Hello"}, {"role": "caller", "text": "Bye"}]

    fake_create.response = SimpleNamespace(
        stop_reason="end_turn",
        content=[SimpleNamespace(type="thinking", thinking=""),
                 SimpleNamespace(type="text", text="Thanks, goodbye! [END_CALL]")])
    assert bot.reply({}, "+1555", transcript) == ("Thanks, goodbye!", True)

    fake_create.response = SimpleNamespace(stop_reason="refusal", content=[])
    text, done = bot.reply({}, "+1555", transcript)
    assert done and "Goodbye" in text
