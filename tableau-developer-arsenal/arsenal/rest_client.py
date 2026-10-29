"""Tableau Server / Tableau Cloud REST API client built on plain requests.

Covers the developer loop: sign in with a personal access token, browse
projects and content, publish workbooks and data sources (chunked upload for
large files), download, refresh extracts and export views.

Reference: https://help.tableau.com/current/api/rest_api/en-us/REST/rest_api_ref.htm
"""

from __future__ import annotations

import uuid
from pathlib import Path
from typing import Iterator
from xml.sax.saxutils import quoteattr

import requests

from .config import ServerConfig

# Files at or below this size go up in one request; larger ones are chunked.
SINGLE_UPLOAD_LIMIT = 64 * 1024 * 1024
CHUNK_SIZE = 5 * 1024 * 1024


class TableauRestError(RuntimeError):
    pass


class TableauServer:
    def __init__(self, config: ServerConfig, timeout: int = 120):
        self.config = config
        self.timeout = timeout
        self.session = requests.Session()
        self.session.headers.update({"Accept": "application/json"})
        self.site_id: str | None = None
        self.user_id: str | None = None

    # -- plumbing ---------------------------------------------------------

    @property
    def api(self) -> str:
        return f"{self.config.server_url}/api/{self.config.api_version}"

    @property
    def site_api(self) -> str:
        if not self.site_id:
            raise TableauRestError("Not signed in.")
        return f"{self.api}/sites/{self.site_id}"

    def _request(self, method: str, url: str, **kwargs) -> requests.Response:
        kwargs.setdefault("timeout", self.timeout)
        resp = self.session.request(method, url, **kwargs)
        if not resp.ok:
            raise TableauRestError(f"{method} {url} -> {resp.status_code}: {resp.text[:500]}")
        return resp

    def _json(self, method: str, url: str, **kwargs) -> dict:
        resp = self._request(method, url, **kwargs)
        return resp.json() if resp.content else {}

    def _paged(self, url: str, key: str, item: str, page_size: int = 100, **params) -> Iterator[dict]:
        page = 1
        while True:
            data = self._json("GET", url, params={"pageSize": page_size, "pageNumber": page, **params})
            yield from data.get(key, {}).get(item, [])
            total = int(data.get("pagination", {}).get("totalAvailable", 0))
            if page * page_size >= total:
                return
            page += 1

    # -- auth -------------------------------------------------------------

    def sign_in(self) -> "TableauServer":
        body = {
            "credentials": {
                "personalAccessTokenName": self.config.pat_name,
                "personalAccessTokenSecret": self.config.pat_secret,
                "site": {"contentUrl": self.config.site},
            }
        }
        creds = self._json("POST", f"{self.api}/auth/signin", json=body)["credentials"]
        self.session.headers["X-Tableau-Auth"] = creds["token"]
        self.site_id = creds["site"]["id"]
        self.user_id = creds["user"]["id"]
        return self

    def sign_out(self) -> None:
        if "X-Tableau-Auth" in self.session.headers:
            self._request("POST", f"{self.api}/auth/signout")
            del self.session.headers["X-Tableau-Auth"]

    def __enter__(self) -> "TableauServer":
        return self.sign_in()

    def __exit__(self, *exc) -> None:
        self.sign_out()

    # -- browse -----------------------------------------------------------

    def server_info(self) -> dict:
        return self._json("GET", f"{self.api}/serverinfo")["serverInfo"]

    def projects(self) -> list[dict]:
        return list(self._paged(f"{self.site_api}/projects", "projects", "project"))

    def project_id(self, name: str) -> str:
        for project in self.projects():
            if project["name"] == name:
                return project["id"]
        raise TableauRestError(f"Project not found: {name}")

    def workbooks(self, filter_expr: str | None = None) -> list[dict]:
        params = {"filter": filter_expr} if filter_expr else {}
        return list(self._paged(f"{self.site_api}/workbooks", "workbooks", "workbook", **params))

    def find_workbook(self, name: str) -> dict:
        matches = self.workbooks(f"name:eq:{name}")
        if not matches:
            raise TableauRestError(f"Workbook not found: {name}")
        return matches[0]

    def views(self, workbook_id: str) -> list[dict]:
        data = self._json("GET", f"{self.site_api}/workbooks/{workbook_id}/views")
        return data.get("views", {}).get("view", [])

    def datasources(self) -> list[dict]:
        return list(self._paged(f"{self.site_api}/datasources", "datasources", "datasource"))

    # -- publish ----------------------------------------------------------

    def publish_workbook(
        self,
        path: str | Path,
        project: str,
        name: str | None = None,
        overwrite: bool = True,
        show_tabs: bool = False,
    ) -> dict:
        path = Path(path)
        name = name or path.stem
        payload = (
            f"<tsRequest><workbook name={quoteattr(name)} showTabs={quoteattr(str(show_tabs).lower())}>"
            f"<project id={quoteattr(self.project_id(project))}/></workbook></tsRequest>"
        )
        params = {"overwrite": str(overwrite).lower()}
        data = self._publish("workbooks", "tableau_workbook", path, payload, params)
        return data["workbook"]

    def publish_datasource(
        self, path: str | Path, project: str, name: str | None = None, overwrite: bool = True
    ) -> dict:
        path = Path(path)
        name = name or path.stem
        payload = (
            f"<tsRequest><datasource name={quoteattr(name)}>"
            f"<project id={quoteattr(self.project_id(project))}/></datasource></tsRequest>"
        )
        params = {"overwrite": str(overwrite).lower()}
        data = self._publish("datasources", "tableau_datasource", path, payload, params)
        return data["datasource"]

    def _publish(self, endpoint: str, file_part: str, path: Path, payload: str, params: dict) -> dict:
        file_type = path.suffix.lstrip(".").lower()
        params = {**params, f"{endpoint[:-1]}Type": file_type}
        url = f"{self.site_api}/{endpoint}"

        if path.stat().st_size <= SINGLE_UPLOAD_LIMIT:
            parts = [("request_payload", None, payload.encode(), "text/xml"),
                     (file_part, path.name, path.read_bytes(), "application/octet-stream")]
        else:
            params["uploadSessionId"] = self._chunked_upload(path)
            parts = [("request_payload", None, payload.encode(), "text/xml")]

        body, content_type = _multipart_mixed(parts)
        return self._json("POST", url, params=params, data=body, headers={"Content-Type": content_type})

    def _chunked_upload(self, path: Path) -> str:
        session_id = self._json("POST", f"{self.site_api}/fileUploads")["fileUpload"]["uploadSessionId"]
        with path.open("rb") as fh:
            while chunk := fh.read(CHUNK_SIZE):
                body, content_type = _multipart_mixed([
                    ("request_payload", None, b"", "text/xml"),
                    ("tableau_file", "file", chunk, "application/octet-stream"),
                ])
                self._request("PUT", f"{self.site_api}/fileUploads/{session_id}",
                              data=body, headers={"Content-Type": content_type})
        return session_id

    # -- download / refresh / export -------------------------------------

    def download_workbook(self, workbook_id: str, dest: str | Path, include_extract: bool = True) -> Path:
        resp = self._request(
            "GET", f"{self.site_api}/workbooks/{workbook_id}/content",
            params={"includeExtract": str(include_extract).lower()}, stream=True,
        )
        return _save_stream(resp, Path(dest))

    def refresh_workbook(self, workbook_id: str) -> dict:
        return self._json("POST", f"{self.site_api}/workbooks/{workbook_id}/refresh",
                          data="<tsRequest/>", headers={"Content-Type": "application/xml"})["job"]

    def refresh_datasource(self, datasource_id: str) -> dict:
        return self._json("POST", f"{self.site_api}/datasources/{datasource_id}/refresh",
                          data="<tsRequest/>", headers={"Content-Type": "application/xml"})["job"]

    def job(self, job_id: str) -> dict:
        return self._json("GET", f"{self.site_api}/jobs/{job_id}")["job"]

    def export_view(self, view_id: str, dest: str | Path, fmt: str = "png", **filters: str) -> Path:
        """Export a view as png, pdf or csv. Keyword args become vf_<field> filters."""
        endpoint = {"png": "image", "pdf": "pdf", "csv": "data"}[fmt]
        params = {f"vf_{field}": value for field, value in filters.items()}
        if fmt == "png":
            params["resolution"] = "high"
        resp = self._request("GET", f"{self.site_api}/views/{view_id}/{endpoint}", params=params, stream=True)
        return _save_stream(resp, Path(dest))


def _multipart_mixed(parts: list[tuple[str, str | None, bytes, str]]) -> tuple[bytes, str]:
    """Build a multipart/mixed body, which publish endpoints require (requests only does form-data)."""
    boundary = uuid.uuid4().hex
    chunks: list[bytes] = []
    for name, filename, content, ctype in parts:
        disposition = f'form-data; name="{name}"'
        if filename:
            disposition += f'; filename="{filename}"'
        chunks.append(
            f"--{boundary}\r\nContent-Disposition: {disposition}\r\nContent-Type: {ctype}\r\n\r\n".encode()
        )
        chunks.append(content)
        chunks.append(b"\r\n")
    chunks.append(f"--{boundary}--\r\n".encode())
    return b"".join(chunks), f"multipart/mixed; boundary={boundary}"


def _save_stream(resp: requests.Response, dest: Path) -> Path:
    dest.parent.mkdir(parents=True, exist_ok=True)
    with dest.open("wb") as fh:
        for block in resp.iter_content(chunk_size=1024 * 1024):
            fh.write(block)
    return dest
