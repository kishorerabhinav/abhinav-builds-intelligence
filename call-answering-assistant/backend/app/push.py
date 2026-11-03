"""Apple Push Notifications: tell the iPhone app a new call summary is ready."""

from __future__ import annotations

import logging
import time
from typing import Any

import httpx
import jwt

from .config import Settings
from .db import Database

log = logging.getLogger(__name__)


class PushSender:
    def __init__(self, settings: Settings, db: Database) -> None:
        self.settings = settings
        self.db = db
        self._token: str | None = None
        self._token_issued = 0.0

    def _auth_token(self) -> str:
        # APNs provider tokens are valid for an hour; refresh every 50 minutes.
        if self._token is None or time.time() - self._token_issued > 50 * 60:
            with open(self.settings.apns_key_path) as fh:
                key = fh.read()
            self._token_issued = time.time()
            self._token = jwt.encode(
                {"iss": self.settings.apns_team_id, "iat": int(self._token_issued)},
                key,
                algorithm="ES256",
                headers={"kid": self.settings.apns_key_id},
            )
        return self._token

    def notify_call(self, call: dict[str, Any]) -> None:
        if not self.settings.push_enabled:
            return
        tokens = self.db.device_tokens()
        if not tokens:
            return
        who = call.get("caller_name") or call.get("from_number") or "Unknown caller"
        urgent = call.get("urgency") == "urgent"
        payload = {
            "aps": {
                "alert": {
                    "title": f"{'URGENT: ' if urgent else ''}{who}",
                    "subtitle": call.get("reason") or "",
                    "body": call.get("summary") or "New message",
                },
                "sound": "default",
                "interruption-level": "time-sensitive" if urgent else "active",
            },
            "call_sid": call["sid"],
        }
        host = "api.sandbox.push.apple.com" if self.settings.apns_use_sandbox else "api.push.apple.com"
        headers = {
            "authorization": f"bearer {self._auth_token()}",
            "apns-topic": self.settings.apns_bundle_id,
            "apns-push-type": "alert",
            "apns-priority": "10",
        }
        with httpx.Client(http2=True, timeout=10.0) as client:
            for token in tokens:
                try:
                    r = client.post(f"https://{host}/3/device/{token}", json=payload, headers=headers)
                    if r.status_code == 410 or (r.status_code == 400 and "BadDeviceToken" in r.text):
                        self.db.remove_device(token)
                    elif r.status_code != 200:
                        log.warning("APNs %s: %s", r.status_code, r.text)
                except httpx.HTTPError:
                    log.exception("APNs request failed")
