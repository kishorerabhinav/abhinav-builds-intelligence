"""Client for Tableau Public's profile API.

These are the JSON endpoints public.tableau.com's own web app uses. They are
public and need no sign-in, but they are undocumented, so treat field names as
subject to change. Tableau Public offers no API for publishing; see
arsenal.public_publish for the supported route.
"""

from __future__ import annotations

from pathlib import Path
from typing import Iterator

import requests

BASE = "https://public.tableau.com"


class TableauPublic:
    def __init__(self, session: requests.Session | None = None, timeout: int = 30):
        self.session = session or requests.Session()
        self.session.headers.setdefault("User-Agent", "tableau-developer-arsenal/0.1")
        self.timeout = timeout

    def _get(self, path: str, **params) -> dict | list:
        resp = self.session.get(f"{BASE}{path}", params=params or None, timeout=self.timeout)
        resp.raise_for_status()
        return resp.json()

    def profile(self, user: str) -> dict:
        return self._get(f"/profile/api/{user}")

    def workbooks(self, user: str, page_size: int = 50) -> Iterator[dict]:
        """Yield every visible workbook on a profile, in profile order."""
        start = 0
        while True:
            page = self._get(
                "/public/apis/workbooks",
                profileName=user, start=start, count=page_size, visibility="NON_HIDDEN",
            )
            batch = page.get("contents", [])
            yield from batch
            # The last page reports next = -1.
            nxt = page.get("next")
            if not batch or nxt is None or nxt <= start:
                return
            start = nxt

    def workbook(self, workbook_repo_url: str) -> dict:
        """Full details for one workbook: publish dates, size, description, settings."""
        return self._get(f"/profile/api/single_workbook/{workbook_repo_url}")

    def followers(self, user: str, page_size: int = 24) -> Iterator[dict]:
        yield from self._paged(f"/profile/api/followers/{user}", page_size)

    def following(self, user: str, page_size: int = 24) -> Iterator[dict]:
        yield from self._paged(f"/profile/api/following/{user}", page_size)

    def _paged(self, path: str, page_size: int) -> Iterator[dict]:
        index = 0
        while True:
            batch = self._get(path, count=page_size, index=index)
            if not batch:
                return
            yield from batch
            if len(batch) < page_size:
                return
            index += page_size

    def view_image(self, workbook_repo_url: str, view_url: str | None, dest: Path) -> Path:
        """Download a static PNG of a published view (default view if view_url is None)."""
        view_url = view_url or self.workbook(workbook_repo_url)["defaultViewRepoUrl"]
        view_url = view_url.rsplit("/", 1)[-1]  # accept "Workbook/sheets/View" too
        resp = self.session.get(
            f"{BASE}/views/{workbook_repo_url}/{view_url}.png",
            params={":display_static_image": "y", ":showVizHome": "n"},
            timeout=self.timeout,
        )
        resp.raise_for_status()
        dest.parent.mkdir(parents=True, exist_ok=True)
        dest.write_bytes(resp.content)
        return dest

    def stats(self, user: str, details: bool = False) -> list[dict]:
        """One summary row per workbook, sorted by views.

        details=True adds publish dates and size (one extra request per workbook).
        """
        rows = []
        for wb in self.workbooks(user):
            repo = wb.get("workbookRepoUrl")
            view = (wb.get("defaultViewRepoUrl") or "").rsplit("/", 1)[-1]
            row = {
                "title": wb.get("title"),
                "repo_url": repo,
                "views": wb.get("viewCount", 0),
                "favorites": wb.get("numberOfFavorites", 0),
                "url": f"{BASE}/app/profile/{user}/viz/{repo}/{view}",
            }
            if details:
                full = self.workbook(repo)
                row.update(
                    first_published=_ms_to_iso(full.get("firstPublishDate")),
                    last_published=_ms_to_iso(full.get("lastPublishDate")),
                    size_bytes=full.get("size"),
                )
            rows.append(row)
        return sorted(rows, key=lambda r: r["views"] or 0, reverse=True)


def _ms_to_iso(value) -> str | None:
    from datetime import datetime, timezone

    if value in (None, ""):
        return None
    return datetime.fromtimestamp(int(value) / 1000, tz=timezone.utc).date().isoformat()
