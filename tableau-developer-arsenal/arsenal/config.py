"""Settings loaded from environment variables (optionally from a .env file)."""

from __future__ import annotations

import os
from dataclasses import dataclass

try:
    from dotenv import load_dotenv

    load_dotenv()
except ImportError:
    pass


def _require(name: str) -> str:
    value = os.environ.get(name)
    if not value:
        raise SystemExit(f"Missing environment variable {name}. See .env.example.")
    return value


@dataclass(frozen=True)
class ServerConfig:
    server_url: str
    site: str
    pat_name: str
    pat_secret: str
    api_version: str = "3.24"

    @classmethod
    def from_env(cls) -> "ServerConfig":
        return cls(
            server_url=_require("TABLEAU_SERVER_URL").rstrip("/"),
            # An empty content URL means the Default site on Tableau Server.
            site=os.environ.get("TABLEAU_SITE", ""),
            pat_name=_require("TABLEAU_PAT_NAME"),
            pat_secret=_require("TABLEAU_PAT_SECRET"),
            api_version=os.environ.get("TABLEAU_API_VERSION", "3.24"),
        )


def public_user(explicit: str | None = None) -> str:
    return explicit or _require("TABLEAU_PUBLIC_USER")
