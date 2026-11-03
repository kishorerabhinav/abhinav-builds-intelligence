"""Settings read from environment variables (see .env.example)."""

from __future__ import annotations

import os
from dataclasses import dataclass
from functools import lru_cache


def _bool(name: str, default: bool) -> bool:
    value = os.environ.get(name)
    if value is None:
        return default
    return value.strip().lower() in {"1", "true", "yes", "on"}


@dataclass(frozen=True)
class Settings:
    # Public HTTPS address Twilio uses to reach this server, e.g. https://calls.example.com
    public_base_url: str
    # Shared secret the iPhone app sends as "Authorization: Bearer <token>"
    app_api_token: str
    database_path: str

    # Twilio: the auth token signs every webhook so we can reject forged requests
    twilio_auth_token: str
    validate_twilio_signature: bool
    tts_voice: str

    claude_model: str

    # Apple Push Notification service (optional)
    apns_key_path: str
    apns_key_id: str
    apns_team_id: str
    apns_bundle_id: str
    apns_use_sandbox: bool

    @property
    def push_enabled(self) -> bool:
        return all([self.apns_key_path, self.apns_key_id, self.apns_team_id, self.apns_bundle_id])


@lru_cache
def get_settings() -> Settings:
    return Settings(
        public_base_url=os.environ.get("PUBLIC_BASE_URL", "").rstrip("/"),
        app_api_token=os.environ.get("APP_API_TOKEN", ""),
        database_path=os.environ.get("DATABASE_PATH", "calls.db"),
        twilio_auth_token=os.environ.get("TWILIO_AUTH_TOKEN", ""),
        validate_twilio_signature=_bool("VALIDATE_TWILIO_SIGNATURE", True),
        tts_voice=os.environ.get("TTS_VOICE", "Polly.Joanna-Neural"),
        claude_model=os.environ.get("CLAUDE_MODEL", "claude-opus-5-5"),
        apns_key_path=os.environ.get("APNS_KEY_PATH", ""),
        apns_key_id=os.environ.get("APNS_KEY_ID", ""),
        apns_team_id=os.environ.get("APNS_TEAM_ID", ""),
        apns_bundle_id=os.environ.get("APNS_BUNDLE_ID", ""),
        apns_use_sandbox=_bool("APNS_USE_SANDBOX", True),
    )
