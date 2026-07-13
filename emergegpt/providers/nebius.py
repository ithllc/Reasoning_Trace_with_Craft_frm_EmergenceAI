"""Nebius Token Factory adapter with redacted responses."""

from __future__ import annotations

import json
import urllib.error
import urllib.parse
import urllib.request

from ..redaction import redact
from ..settings import Settings


class NebiusProvider:
    def __init__(self, settings: Settings):
        self.settings = settings

    def request(self, method: str, path: str, payload: dict | None = None) -> dict:
        if not self.settings.nebius_api_key:
            raise RuntimeError("Nebius credential is not configured")
        url = self.settings.nebius_base_url + "/" + path.lstrip("/")
        if self.settings.nebius_project_id and not self.settings.nebius_project_id.startswith("replace-"):
            url += ("&" if "?" in url else "?") + urllib.parse.urlencode({"ai_project_id": self.settings.nebius_project_id})
        body = json.dumps(payload).encode() if payload is not None else None
        request = urllib.request.Request(url, data=body, method=method, headers={
            "Authorization": f"Bearer {self.settings.nebius_api_key}", "Accept": "application/json",
            **({"Content-Type": "application/json"} if body else {}),
        })
        try:
            with urllib.request.urlopen(request, timeout=60) as response:
                data = response.read()
        except urllib.error.HTTPError as error:
            raise RuntimeError(f"Nebius request failed ({error.code})") from error
        return json.loads(data) if data else {}

    def models(self) -> list[dict]:
        return redact(self.request("GET", "models?verbose=true").get("data", []))

    def jobs(self) -> list[dict]:
        return redact(self.request("GET", "fine_tuning/jobs?limit=50").get("data", []))

    def job(self, job_id: str) -> dict:
        return redact(self.request("GET", f"fine_tuning/jobs/{job_id}"))

    def checkpoints(self, job_id: str) -> dict:
        return redact(self.request("GET", f"fine_tuning/jobs/{job_id}/checkpoints"))
