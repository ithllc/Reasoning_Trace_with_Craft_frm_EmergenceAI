"""Bounded subprocess harness contract."""

from __future__ import annotations

import json
import os
import shutil
import subprocess
import time
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class HarnessRequest:
    request_id: str
    workspace: Path
    prompt: str
    model: str | None = None
    timeout_seconds: int = 300


class SubprocessHarness:
    name = "base"
    binary = ""

    def capabilities(self) -> dict:
        path = shutil.which(self.binary)
        return {"name": self.name, "available": bool(path), "binary": path, "structured_output": True}

    def command(self, request: HarnessRequest) -> list[str]:
        raise NotImplementedError

    def normalize(self, output: str) -> dict:
        return json.loads(output)

    def run(self, request: HarnessRequest) -> dict:
        if not request.workspace.resolve().is_dir():
            raise ValueError("workspace does not exist")
        if not shutil.which(self.binary):
            raise RuntimeError(f"{self.binary} is not installed")
        started = time.time()
        environment = {key: value for key, value in os.environ.items() if key in {"PATH", "HOME", "LANG", "TERM"} or key.endswith("_API_KEY")}
        result = subprocess.run(self.command(request), cwd=request.workspace, env=environment, capture_output=True, text=True,
                                timeout=request.timeout_seconds, check=False, start_new_session=True)
        if result.returncode:
            raise RuntimeError(f"{self.name} exited {result.returncode}: {result.stderr[-500:]}")
        return {"request_id": request.request_id, "harness": {"name": self.name}, "status": "succeeded",
                "started_at": started, "finished_at": time.time(), "result": self.normalize(result.stdout),
                "stderr_summary": result.stderr[-1000:] or None}
