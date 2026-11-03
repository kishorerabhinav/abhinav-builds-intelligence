"""The Claude side of the call: what the assistant says, and the summary afterwards."""

from __future__ import annotations

import json
import logging
from typing import Any, Protocol

import anthropic

log = logging.getLogger(__name__)

END_MARKER = "[END_CALL]"

# Server-side fallback: if the model declines a turn, the API re-runs it on
# Anthropic's recommended fallback model instead of returning a refusal.
_FALLBACK_BETA = "server-side-fallback-2026-07-01"

_SAFE_REPLY = (
    "Sorry, I didn't quite catch that. Could you tell me your name and why you're calling? "
)
_GOODBYE = "Thanks for calling. I'll pass your message along. Goodbye!"

SUMMARY_SCHEMA: dict[str, Any] = {
    "type": "object",
    "properties": {
        "caller_name": {"type": "string", "description": "Caller's name, or empty if not given"},
        "callback_number": {"type": "string", "description": "Number to call back, or empty"},
        "reason": {"type": "string", "description": "A few words: why they called"},
        "urgency": {"type": "string", "enum": ["low", "normal", "urgent", "spam"]},
        "summary": {"type": "string", "description": "One to three sentences for the phone's owner"},
    },
    "required": ["caller_name", "callback_number", "reason", "urgency", "summary"],
    "additionalProperties": False,
}


class Assistant(Protocol):
    def greeting(self, settings: dict[str, str]) -> str: ...
    def reply(self, settings: dict[str, str], caller: str, transcript: list[dict[str, str]]) -> tuple[str, bool]: ...
    def summarize(self, caller: str, transcript: list[dict[str, str]]) -> dict[str, str]: ...


def default_greeting(settings: dict[str, str]) -> str:
    if settings.get("greeting", "").strip():
        return settings["greeting"].strip()
    owner = settings.get("owner_name") or "the person you're calling"
    return (
        f"Hi, you've reached {owner}'s assistant. {owner} can't come to the phone right now. "
        "May I ask who's calling and what it's about?"
    )


def _system_prompt(settings: dict[str, str], caller: str) -> str:
    owner = settings.get("owner_name") or "the phone's owner"
    extra = settings.get("instructions", "").strip()
    prompt = f"""You are the phone assistant answering calls for {owner}, who can't pick up right now.
You are speaking on a live phone call: your words are read aloud by text-to-speech, and the caller's
words reach you through speech recognition, which can garble names and numbers.

Your job:
- Find out who is calling and why, and whether it's urgent.
- If they want a call back, confirm the best number. Their caller ID is {caller or "unknown"};
  read it back in digits and ask if that's the right number rather than asking them to recite it.
- Take a short message if they want to leave one.
- Answer simple questions only if the instructions below give you the answer. Never promise that
  {owner} will do something, never share personal details about {owner}, and never agree to payments,
  codes, or account changes.
- If the call looks like spam, a robocall, or a scam, politely end it.

How to speak:
- One or two short sentences per turn, plain conversational words. No lists, markdown, emoji, or
  symbols - everything you write is spoken.
- Ask one question at a time.

When you have what you need, or the caller says goodbye, say a brief goodbye and put {END_MARKER}
at the very end of that reply. The call hangs up after it."""
    if extra:
        prompt += f"\n\nInstructions from {owner}:\n{extra}"
    return prompt


def _to_messages(transcript: list[dict[str, str]]) -> list[dict[str, str]]:
    """Turn the call transcript into alternating user/assistant messages.

    The transcript starts with the assistant's greeting; the API needs a user turn
    first, so the greeting is folded into a short opening note.
    """
    messages: list[dict[str, str]] = []
    for turn in transcript:
        role = "assistant" if turn["role"] == "assistant" else "user"
        if not messages and role == "assistant":
            messages.append({"role": "user", "content": "(The call connects.)"})
        if messages and messages[-1]["role"] == role:
            messages[-1]["content"] += " " + turn["text"]
        else:
            messages.append({"role": role, "content": turn["text"]})
    return messages


def _text_of(response: Any) -> str:
    return "".join(b.text for b in response.content if getattr(b, "type", "") == "text").strip()


class ClaudeAssistant:
    def __init__(self, model: str, client: anthropic.Anthropic | None = None) -> None:
        self.model = model
        # Twilio waits ~15s for a webhook response, so keep each turn on a short leash.
        self.client = client or anthropic.Anthropic(timeout=12.0, max_retries=1)

    def greeting(self, settings: dict[str, str]) -> str:
        return default_greeting(settings)

    def reply(
        self, settings: dict[str, str], caller: str, transcript: list[dict[str, str]]
    ) -> tuple[str, bool]:
        try:
            response = self.client.beta.messages.create(
                model=self.model,
                max_tokens=2000,
                system=_system_prompt(settings, caller),
                messages=_to_messages(transcript),
                # Low effort keeps the pause between turns short on a live call.
                output_config={"effort": "low"},
                betas=[_FALLBACK_BETA],
                fallbacks="default",
            )
        except anthropic.APIError:
            log.exception("Claude reply failed")
            return _SAFE_REPLY, False

        if response.stop_reason == "refusal":
            return _GOODBYE, True
        text = _text_of(response)
        done = END_MARKER in text
        text = text.replace(END_MARKER, "").strip()
        if not text:
            return (_GOODBYE, True) if done else (_SAFE_REPLY, False)
        return text, done

    def summarize(self, caller: str, transcript: list[dict[str, str]]) -> dict[str, str]:
        caller_spoke = any(t["role"] == "caller" for t in transcript)
        if not caller_spoke:
            return {
                "caller_name": "",
                "callback_number": caller,
                "reason": "No message",
                "urgency": "low",
                "summary": "The caller hung up without saying anything.",
            }
        lines = "\n".join(
            f"{'Assistant' if t['role'] == 'assistant' else 'Caller'}: {t['text']}" for t in transcript
        )
        try:
            response = self.client.with_options(timeout=60.0).beta.messages.create(
                model=self.model,
                max_tokens=4000,
                system=(
                    "You summarize phone calls that an assistant answered for the phone's owner. "
                    "Write for the owner, glancing at a notification. Speech recognition may have "
                    "garbled words; use the caller ID when a callback number wasn't confirmed."
                ),
                messages=[{
                    "role": "user",
                    "content": f"Caller ID: {caller or 'unknown'}\n\nTranscript:\n{lines}",
                }],
                output_config={
                    "effort": "medium",
                    "format": {"type": "json_schema", "schema": SUMMARY_SCHEMA},
                },
                betas=[_FALLBACK_BETA],
                fallbacks="default",
            )
            if response.stop_reason == "refusal":
                raise ValueError("summary declined")
            return json.loads(_text_of(response))
        except (anthropic.APIError, ValueError):
            log.exception("Claude summary failed")
            first = next((t["text"] for t in transcript if t["role"] == "caller"), "")
            return {
                "caller_name": "",
                "callback_number": caller,
                "reason": "Message",
                "urgency": "normal",
                "summary": first[:300],
            }
