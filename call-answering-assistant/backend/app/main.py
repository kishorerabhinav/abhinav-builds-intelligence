"""HTTP server: Twilio voice webhooks plus the JSON API the iPhone app reads."""

from __future__ import annotations

import hmac
import logging
from typing import Any

from fastapi import BackgroundTasks, Depends, FastAPI, HTTPException, Request, Response
from pydantic import BaseModel, Field
from twilio.request_validator import RequestValidator
from twilio.twiml.voice_response import Gather, VoiceResponse

from .agent import Assistant, ClaudeAssistant
from .config import Settings, get_settings
from .db import Database, now_iso
from .push import PushSender

log = logging.getLogger(__name__)

FINAL_STATUSES = {"completed", "busy", "failed", "no-answer", "canceled"}
MAX_SILENT_TURNS = 2
MAX_CALLER_TURNS = 12


class SettingsBody(BaseModel):
    owner_name: str | None = Field(default=None, max_length=80)
    greeting: str | None = Field(default=None, max_length=500)
    instructions: str | None = Field(default=None, max_length=4000)


class CallPatch(BaseModel):
    is_read: bool


class DeviceBody(BaseModel):
    token: str = Field(min_length=8, max_length=200, pattern=r"^[0-9a-fA-F]+$")


def create_app(
    settings: Settings | None = None,
    db: Database | None = None,
    assistant: Assistant | None = None,
    push: PushSender | None = None,
) -> FastAPI:
    settings = settings or get_settings()
    db = db or Database(settings.database_path)
    assistant = assistant or ClaudeAssistant(settings.claude_model)
    push = push or PushSender(settings, db)
    validator = RequestValidator(settings.twilio_auth_token)

    app = FastAPI(title="Call Answering Assistant")

    # ---- helpers -----------------------------------------------------------

    async def twilio_form(request: Request) -> dict[str, str]:
        form = {k: str(v) for k, v in (await request.form()).items()}
        if settings.validate_twilio_signature:
            url = settings.public_base_url + request.url.path
            if request.url.query:
                url += "?" + request.url.query
            signature = request.headers.get("X-Twilio-Signature", "")
            if not settings.twilio_auth_token or not validator.validate(url, form, signature):
                raise HTTPException(status_code=403, detail="Invalid Twilio signature")
        return form

    def require_app_token(request: Request) -> None:
        if not settings.app_api_token:
            raise HTTPException(status_code=503, detail="APP_API_TOKEN is not configured")
        supplied = request.headers.get("Authorization", "").removeprefix("Bearer ").strip()
        if not hmac.compare_digest(supplied.encode(), settings.app_api_token.encode()):
            raise HTTPException(status_code=401, detail="Bad token")

    def twiml(vr: VoiceResponse) -> Response:
        return Response(content=str(vr), media_type="application/xml")

    def say_and_listen(vr: VoiceResponse, text: str) -> VoiceResponse:
        gather = Gather(
            input="speech",
            action="/twilio/turn",
            method="POST",
            speech_timeout="auto",
            timeout=6,
            language="en-US",
            speech_model="phone_call",
            enhanced=True,
            action_on_empty_result=True,
        )
        gather.say(text, voice=settings.tts_voice)
        vr.append(gather)
        # Reached only if Gather gets nothing at all; treat it as silence.
        vr.redirect("/twilio/turn", method="POST")
        return vr

    def say_goodbye(vr: VoiceResponse, text: str) -> VoiceResponse:
        vr.say(text, voice=settings.tts_voice)
        vr.hangup()
        return vr

    def finish_call(sid: str, status: str) -> None:
        call = db.get_call(sid)
        if not call or call["ended_at"]:
            return
        db.update_call(sid, ended_at=now_iso(), status="summarizing")
        result = assistant.summarize(call["from_number"], call["transcript"])
        db.update_call(
            sid,
            status="completed" if status == "completed" else status,
            caller_name=result.get("caller_name", ""),
            callback_number=result.get("callback_number", ""),
            reason=result.get("reason", ""),
            urgency=result.get("urgency", "normal"),
            summary=result.get("summary", ""),
        )
        final = db.get_call(sid)
        if final and final["urgency"] != "spam":
            push.notify_call(final)

    # ---- Twilio webhooks ---------------------------------------------------

    @app.post("/twilio/voice")
    async def incoming_call(request: Request) -> Response:
        form = await twilio_form(request)
        sid = form.get("CallSid", "")
        db.create_call(sid, form.get("From", ""), form.get("ForwardedFrom") or form.get("To", ""))
        greeting = assistant.greeting(db.get_settings())
        db.append_turn(sid, "assistant", greeting)
        return twiml(say_and_listen(VoiceResponse(), greeting))

    @app.post("/twilio/turn")
    async def caller_turn(request: Request) -> Response:
        form = await twilio_form(request)
        sid = form.get("CallSid", "")
        call = db.get_call(sid)
        if call is None:
            db.create_call(sid, form.get("From", ""), form.get("To", ""))
            call = db.get_call(sid)
        speech = form.get("SpeechResult", "").strip()

        if not speech:
            if db.bump_silence(sid) >= MAX_SILENT_TURNS:
                return twiml(say_goodbye(VoiceResponse(), "I'll let them know you called. Goodbye!"))
            return twiml(say_and_listen(VoiceResponse(), "Sorry, are you still there?"))

        transcript = db.append_turn(sid, "caller", speech)
        caller_turns = sum(1 for t in transcript if t["role"] == "caller")
        reply, done = assistant.reply(db.get_settings(), call["from_number"], transcript)
        db.append_turn(sid, "assistant", reply)
        if done or caller_turns >= MAX_CALLER_TURNS:
            return twiml(say_goodbye(VoiceResponse(), reply))
        return twiml(say_and_listen(VoiceResponse(), reply))

    @app.post("/twilio/status")
    async def call_status(request: Request, background: BackgroundTasks) -> Response:
        form = await twilio_form(request)
        status = form.get("CallStatus", "")
        if status in FINAL_STATUSES:
            background.add_task(finish_call, form.get("CallSid", ""), status)
        return Response(status_code=204)

    # ---- iPhone app API ----------------------------------------------------

    @app.get("/api/health")
    def health() -> dict[str, Any]:
        return {"ok": True, "push_enabled": settings.push_enabled}

    @app.get("/api/calls", dependencies=[Depends(require_app_token)])
    def list_calls(limit: int = 100) -> list[dict[str, Any]]:
        return db.list_calls(min(max(limit, 1), 500))

    @app.get("/api/calls/{sid}", dependencies=[Depends(require_app_token)])
    def get_call(sid: str) -> dict[str, Any]:
        call = db.get_call(sid)
        if call is None:
            raise HTTPException(status_code=404, detail="Not found")
        return call

    @app.patch("/api/calls/{sid}", dependencies=[Depends(require_app_token)])
    def patch_call(sid: str, body: CallPatch) -> dict[str, Any]:
        if db.get_call(sid) is None:
            raise HTTPException(status_code=404, detail="Not found")
        db.update_call(sid, is_read=int(body.is_read))
        return db.get_call(sid)  # type: ignore[return-value]

    @app.delete("/api/calls/{sid}", status_code=204, dependencies=[Depends(require_app_token)])
    def delete_call(sid: str) -> Response:
        if not db.delete_call(sid):
            raise HTTPException(status_code=404, detail="Not found")
        return Response(status_code=204)

    @app.get("/api/settings", dependencies=[Depends(require_app_token)])
    def read_settings() -> dict[str, str]:
        return db.get_settings()

    @app.put("/api/settings", dependencies=[Depends(require_app_token)])
    def write_settings(body: SettingsBody) -> dict[str, str]:
        return db.save_settings(body.model_dump(exclude_none=True))

    @app.post("/api/devices", status_code=204, dependencies=[Depends(require_app_token)])
    def register_device(body: DeviceBody) -> Response:
        db.add_device(body.token.lower())
        return Response(status_code=204)

    return app


def build_app() -> FastAPI:
    """Entry point: `uvicorn app.main:build_app --factory`."""
    logging.basicConfig(level=logging.INFO)
    return create_app()
