#!/usr/bin/env python3
"""Local management UI for CRAFT traces, Nebius jobs, datasets, and evaluations."""

from __future__ import annotations

import json
import subprocess
import sys
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import urlparse

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from scripts import pipeline  # noqa: E402

STATIC = Path(__file__).resolve().parent / "static"
TEACHER_DATA = ROOT / "data" / "generated" / "digital-analytics-200-teacher.jsonl"


def dashboard() -> dict:
    pipeline.load_dotenv()
    config = pipeline.load_json(ROOT / "config" / "pipeline.json")
    manifest_path = ROOT / "artifacts" / "digital-analytics-200-dataset" / "manifest.json"
    manifest = pipeline.load_json(manifest_path) if manifest_path.exists() else None
    examples = pipeline.read_jsonl(TEACHER_DATA) if TEACHER_DATA.exists() else []
    evaluations = pipeline.load_json(ROOT / "evals" / "qwythos-suite.json")
    result_paths = sorted((ROOT / "evals" / "results").glob("ftjob-*.json"))
    training_history = [pipeline.load_json(path) for path in result_paths]
    training_history.sort(key=lambda item: item.get("session_order", 0))
    training_result = next((item for item in training_history if item.get("job_id") == "ftjob-4bfaa9ef51994ed5bd1924f58d686c2e"), None)
    try:
        jobs = pipeline.api_request("GET", "fine_tuning/jobs?limit=20").get("data", [])
        jobs_error = None
    except RuntimeError as error:
        jobs, jobs_error = [], str(error)
    return {
        "project": config["project"],
        "teacher": config["teacher"],
        "student": config["student"],
        "craft": config["craft"],
        "training": config["nebius"]["training"],
        "manifest": manifest,
        "examples": [{
            "id": row.get("metadata", {}).get("id"),
            "domain": row.get("metadata", {}).get("domain"),
            "validation": row.get("metadata", {}).get("trace", {}).get("validation"),
            "decision_summary": row.get("metadata", {}).get("trace", {}).get("decision_summary"),
        } for row in examples],
        "evaluations": evaluations,
        "training_result": training_result,
        "training_history": training_history,
        "jobs": [{
            key: job.get(key) for key in (
                "id", "model", "status", "created_at", "finished_at", "trained_steps", "total_steps", "trained_tokens", "error"
            )
        } for job in jobs],
        "jobs_error": jobs_error,
    }


def update_review(example_id: str, status: str) -> None:
    if status not in {"passed", "needs_review"}:
        raise ValueError("status must be passed or needs_review")
    rows = pipeline.read_jsonl(TEACHER_DATA)
    found = False
    for row in rows:
        if row.get("metadata", {}).get("id") == example_id:
            row["metadata"]["trace"]["validation"] = status
            found = True
    if not found:
        raise ValueError(f"unknown example: {example_id}")
    temporary = TEACHER_DATA.with_suffix(".tmp")
    pipeline.write_jsonl(temporary, rows)
    temporary.replace(TEACHER_DATA)
    subprocess.run([
        sys.executable, str(ROOT / "scripts" / "pipeline.py"), "prepare",
        "--input", str(TEACHER_DATA),
    ], cwd=ROOT, check=True)


class Handler(BaseHTTPRequestHandler):
    def send_json(self, value: object, status: int = 200) -> None:
        body = json.dumps(value).encode()
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self) -> None:  # noqa: N802
        path = urlparse(self.path).path
        if path == "/api/dashboard":
            try:
                self.send_json(dashboard())
            except Exception as error:
                self.send_json({"error": str(error)}, 500)
            return
        file_path = STATIC / ("index.html" if path == "/" else path.lstrip("/"))
        if not file_path.is_file() or STATIC not in file_path.resolve().parents:
            self.send_error(HTTPStatus.NOT_FOUND)
            return
        body = file_path.read_bytes()
        content_type = "text/html; charset=utf-8" if file_path.suffix == ".html" else "text/plain"
        self.send_response(200)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_POST(self) -> None:  # noqa: N802
        path = urlparse(self.path).path
        length = int(self.headers.get("Content-Length", "0"))
        payload = json.loads(self.rfile.read(length) or b"{}")
        try:
            if path.startswith("/api/reviews/"):
                update_review(path.rsplit("/", 1)[-1], payload["status"])
                self.send_json({"ok": True})
                return
            if path.startswith("/api/jobs/") and path.endswith("/cancel"):
                job_id = path.split("/")[3]
                result = pipeline.api_request("POST", f"fine_tuning/jobs/{job_id}/cancel")
                self.send_json({"ok": True, "status": result.get("status")})
                return
            self.send_error(HTTPStatus.NOT_FOUND)
        except Exception as error:
            self.send_json({"error": str(error)}, 400)


def main() -> None:
    server = ThreadingHTTPServer(("127.0.0.1", 8765), Handler)
    print("CRAFT tuning dashboard: http://127.0.0.1:8765")
    server.serve_forever()


if __name__ == "__main__":
    main()
