#!/usr/bin/env python3
"""Local management UI for CRAFT traces, Nebius jobs, datasets, and evaluations."""

from __future__ import annotations

import json
import os
import subprocess
import sys
import threading
import time
import uuid
from datetime import datetime, timezone
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, urlparse

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from scripts import pipeline  # noqa: E402
from emergegpt import __version__  # noqa: E402
from emergegpt.audit import record as audit_record  # noqa: E402
from emergegpt.costs import comparison as cost_comparison  # noqa: E402
from emergegpt.db import Database  # noqa: E402
from emergegpt.docs_index.indexer import build as build_docs, search as search_docs  # noqa: E402
from emergegpt.evaluations import classify, wilson_interval  # noqa: E402
from emergegpt.evaluation_service import EvaluationService  # noqa: E402
from emergegpt.harnesses.adapters import ALL_HARNESSES  # noqa: E402
from emergegpt.health import root_cause_recommendation, score as health_score  # noqa: E402
from emergegpt.mcp_builder import create_draft, get_draft, install as install_mcp, preview as preview_mcp, update_draft, validate as validate_mcp  # noqa: E402
from emergegpt.providers.craft import CraftProvider  # noqa: E402
from emergegpt.providers.nebius import NebiusProvider  # noqa: E402
from emergegpt.notification_adapters import EmailAdapter, SlackAdapter, TelegramAdapter  # noqa: E402
from emergegpt.notification_service import NotificationService, TOPIC_FLOORS  # noqa: E402
from emergegpt.pipeline_runs import PipelineRunService, record_cost_comparison, student_profiles, teacher_profiles  # noqa: E402
from emergegpt.settings import Settings  # noqa: E402
from emergegpt.scheduling import next_fires  # noqa: E402
from emergegpt.schedule_service import ScheduleService  # noqa: E402
from emergegpt.workflows import create as create_workflow, transition as transition_workflow  # noqa: E402

STATIC = Path(__file__).resolve().parent / "static"
TEACHER_DATA = ROOT / "data" / "generated" / "digital-analytics-1000-teacher.jsonl"


def runtime() -> tuple[Settings, Database]:
    pipeline.load_dotenv()
    settings = Settings.load()
    database = Database(settings.database_path)
    database.migrate()
    return settings, database


def notifier(database: Database) -> NotificationService:
    return NotificationService(database, {"email": EmailAdapter, "slack": SlackAdapter, "telegram": TelegramAdapter})


def dashboard() -> dict:
    pipeline.load_dotenv()
    settings, database = runtime()
    config = pipeline.load_json(ROOT / "config" / "pipeline.json")
    manifest_path = ROOT / "artifacts" / "digital-analytics-1000-dataset" / "manifest.json"
    manifest = pipeline.load_json(manifest_path) if manifest_path.exists() else None
    examples = pipeline.read_jsonl(TEACHER_DATA) if TEACHER_DATA.exists() else []
    evaluations = {"program": "EmergeGPT project-owned evaluations", "definitions": []}
    result_paths = sorted((ROOT / "evals" / "results").glob("ftjob-*.json"))
    training_history = [pipeline.load_json(path) for path in result_paths]
    training_history.sort(key=lambda item: item.get("session_order", 0))
    training_result = training_history[-1] if training_history else None
    try:
        jobs = pipeline.api_request("GET", "fine_tuning/jobs?limit=20").get("data", [])
        jobs_error = None
    except RuntimeError as error:
        jobs, jobs_error = [], str(error)
    return {
        "project": "EmergeGPT",
        "version": __version__,
        "teacher": config["teacher"],
        "student": config["student"],
        "craft": CraftProvider(settings).connection_status(),
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
        "configuration": settings.public_configuration(),
        "harnesses": [adapter().capabilities() for adapter in ALL_HARNESSES.values()],
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
    def security_headers(self) -> None:
        self.send_header("X-Content-Type-Options", "nosniff")
        self.send_header("X-Frame-Options", "DENY")
        self.send_header("Referrer-Policy", "no-referrer")
        self.send_header("Content-Security-Policy", "default-src 'self'; script-src 'self' 'unsafe-inline'; style-src 'self' 'unsafe-inline'; connect-src 'self' http://127.0.0.1:8766; img-src 'self' data:; frame-ancestors 'none'")

    def send_json(self, value: object, status: int = 200) -> None:
        body = json.dumps(value).encode()
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.security_headers()
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self) -> None:  # noqa: N802
        parsed = urlparse(self.path)
        path = parsed.path
        if path == "/api/dashboard":
            try:
                self.send_json(dashboard())
            except Exception as error:
                self.send_json({"error": str(error)}, 500)
            return
        if path == "/api/docs/status":
            try:
                _, database = runtime()
                manifest = build_docs(ROOT, database)
                self.send_json(manifest)
            except Exception as error:
                self.send_json({"error": str(error)}, 500)
            return
        if path == "/api/docs/search":
            try:
                _, database = runtime()
                query = parse_qs(parsed.query).get("q", [""])[0]
                self.send_json({"results": search_docs(database, query)})
            except Exception as error:
                self.send_json({"error": str(error)}, 400)
            return
        if path == "/api/harnesses":
            self.send_json({"harnesses": [adapter().capabilities() for adapter in ALL_HARNESSES.values()]})
            return
        if path in {"/api/models/teachers", "/api/models/catalog"}:
            try:
                settings, _ = runtime()
                live_models = NebiusProvider(settings).models()
                self.send_json({"teachers": teacher_profiles(settings, live_models), "students": student_profiles(),
                                "live_refreshed": True, "teacher_count_live": len(live_models)})
            except Exception as error:
                settings, _ = runtime()
                self.send_json({"teachers": teacher_profiles(settings), "students": student_profiles(),
                                "live_refreshed": False, "warning": str(error)})
            return
        if path == "/api/pipeline-runs":
            settings, database = runtime()
            self.send_json({"runs": PipelineRunService(database, settings).list()})
            return
        if path.startswith("/api/pipeline-runs/"):
            try:
                settings, database = runtime()
                self.send_json(PipelineRunService(database, settings).get(path.rsplit("/", 1)[-1]))
            except Exception as error:
                self.send_json({"error": str(error)}, 404)
            return
        if path.startswith("/api/integrations/mcp/drafts/"):
            try:
                _, database = runtime()
                self.send_json(get_draft(database, path.rsplit("/", 1)[-1]))
            except Exception as error:
                self.send_json({"error": str(error)}, 404)
            return
        if path == "/api/audit":
            _, database = runtime()
            with database.connect() as connection:
                rows = [dict(row) for row in connection.execute("SELECT * FROM audit_events ORDER BY occurred_at DESC LIMIT 100")]
            self.send_json({"events": rows})
            return
        if path == "/api/schedules":
            _, database = runtime()
            self.send_json({"schedules": ScheduleService(database).list()})
            return
        if path == "/api/notifications":
            _, database = runtime()
            service = notifier(database)
            self.send_json({"profiles": service.list_profiles(), "topics": TOPIC_FLOORS,
                            "alerts": service.list_alerts()})
            return
        if path == "/api/evaluations":
            _, database = runtime()
            service = EvaluationService(database)
            service.sync_builtins()
            self.send_json({"definitions": service.list_definitions(), "runs": service.list_runs()})
            return
        if path == "/api/evaluations/promotion-readiness":
            _, database = runtime()
            model_id = parse_qs(parsed.query).get("model_id", [""])[0]
            if not model_id:
                self.send_json({"error": "model_id is required"}, 400); return
            service = EvaluationService(database); service.sync_builtins()
            self.send_json(service.promotion_readiness(model_id)); return
        if path.startswith("/api/schedules/"):
            try:
                _, database = runtime()
                self.send_json(ScheduleService(database).get(path.split("/")[3]))
            except Exception as error:
                self.send_json({"error": str(error)}, 404)
            return
        file_path = STATIC / ("index.html" if path == "/" else path.lstrip("/"))
        if not file_path.is_file() or STATIC not in file_path.resolve().parents:
            self.send_error(HTTPStatus.NOT_FOUND)
            return
        body = file_path.read_bytes()
        content_type = "text/html; charset=utf-8" if file_path.suffix == ".html" else "text/plain"
        self.send_response(200)
        self.send_header("Content-Type", content_type)
        self.security_headers()
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_POST(self) -> None:  # noqa: N802
        path = urlparse(self.path).path
        length = int(self.headers.get("Content-Length", "0"))
        if length > 1_048_576:
            self.send_json({"error": "request body exceeds 1 MiB"}, 413)
            return
        origin = self.headers.get("Origin")
        settings, _ = runtime()
        if origin and origin != settings.public_origin:
            self.send_json({"error": "browser origin is not allowed"}, 403)
            return
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
            if path == "/api/docs/refresh":
                settings, database = runtime()
                result = build_docs(ROOT, database)
                audit_record(database, actor="local-user", action="docs.refresh", resource_type="documentation",
                             resource_id=result["build_hash"], outcome="succeeded", details={"source_count": result["source_count"]})
                self.send_json(result)
                return
            if path == "/api/integrations/mcp/drafts":
                _, database = runtime()
                result = create_draft(database, payload["server_kind"], payload.get("config", {}))
                audit_record(database, actor="local-user", action="mcp.draft.create", resource_type="mcp_draft",
                             resource_id=result["id"], outcome="succeeded", details={"server_kind": result["server_kind"]})
                self.send_json(result, 201)
                return
            if path == "/api/pipeline-approvals":
                settings, database = runtime()
                result = PipelineRunService(database, settings).issue_live_approval(payload)
                audit_record(database, actor="local-user", action="pipeline.approve", resource_type="pipeline_request",
                             resource_id=result["request_hash"], outcome="succeeded", details={"scope": result["scope"]})
                self.send_json(result, 201)
                return
            if path == "/api/pipeline-runs":
                settings, database = runtime()
                result = PipelineRunService(database, settings, notifier=notifier(database)).create(payload)
                audit_record(database, actor="local-user", action="pipeline.start", resource_type="pipeline_run",
                             resource_id=result["id"], outcome="queued", details={"request_hash": result["request_hash"]})
                self.send_json(result, 201)
                return
            if path == "/api/notifications/profiles":
                _, database = runtime()
                self.send_json(notifier(database).create_profile(payload), 201); return
            if path.startswith("/api/notifications/profiles/"):
                _, database = runtime()
                parts, service = path.split("/"), notifier(database)
                profile_id, action = parts[4], parts[5] if len(parts) > 5 else "update"
                if action == "enable": result = service.set_enabled(profile_id, True)
                elif action == "disable": result = service.set_enabled(profile_id, False)
                elif action == "subscribe": result = service.subscribe(profile_id, payload["topic"], payload.get("minimum_severity", "info"))
                elif action == "unsubscribe": service.unsubscribe(profile_id, payload["topic"]); result = {"unsubscribed": True}
                else: raise ValueError("unknown notification profile action")
                self.send_json(result); return
            if path.startswith("/api/notifications/alerts/"):
                _, database = runtime()
                self.send_json(notifier(database).set_alert_state(path.split("/")[4], payload["state"])); return
            if path == "/api/evaluations/definitions":
                _, database = runtime()
                self.send_json(EvaluationService(database).upsert_definition(payload), 201); return
            if path == "/api/evaluations/recommend":
                _, database = runtime()
                harness_name = payload.get("harness")
                factory = ALL_HARNESSES.get(harness_name) if payload.get("use_harness") else None
                if payload.get("use_harness") and not factory: raise ValueError("unknown evaluation advice harness")
                self.send_json(EvaluationService(database).recommend(payload, factory), 201); return
            if path == "/api/evaluations/runs":
                _, database = runtime()
                harness_name = payload.get("harness")
                factory = ALL_HARNESSES.get(harness_name) if harness_name else None
                if harness_name and not factory: raise ValueError("unknown evaluation execution harness")
                self.send_json(EvaluationService(database).create_run(payload, factory), 201); return
            if path.startswith("/api/integrations/mcp/drafts/"):
                settings, database = runtime()
                parts = path.split("/")
                draft_id, action = parts[5], parts[6] if len(parts) > 6 else "update"
                if action == "preview":
                    self.send_json(preview_mcp(database, draft_id)); return
                if action == "validate":
                    self.send_json(validate_mcp(database, draft_id, settings)); return
                if action == "install":
                    result = install_mcp(database, draft_id, payload["config_hash"])
                    audit_record(database, actor="local-user", action="mcp.install", resource_type="mcp_installation",
                                 resource_id=result["id"], outcome="succeeded", details={"server_kind": result["server_kind"]})
                    self.send_json(result); return
                self.send_json(update_draft(database, draft_id, payload["step"], payload.get("config", {}))); return
            if path == "/api/workflows":
                _, database = runtime()
                result = create_workflow(database, payload["definition_id"], payload.get("config", {}), payload["idempotency_key"])
                self.send_json(result, 201); return
            if path == "/api/schedules":
                _, database = runtime()
                self.send_json(ScheduleService(database).create(payload), 201); return
            if path.startswith("/api/schedules/"):
                settings, database = runtime()
                parts, service = path.split("/"), ScheduleService(database)
                schedule_id, action = parts[3], parts[4] if len(parts) > 4 else "update"
                if action == "pause": result = service.set_enabled(schedule_id, False)
                elif action == "resume": result = service.set_enabled(schedule_id, True)
                elif action == "run-now":
                    def dispatch(workflow, key):
                        if workflow.get("pipeline"):
                            run = PipelineRunService(database, settings).create({**workflow["pipeline"], "idempotency_key": key})
                            return {"status": run["state"], "workflow_run_id": run["id"]}
                        return {"status": "waiting_approval", "workflow_run_id": None}
                    result = service.run_now(schedule_id, dispatch)
                else: result = service.update(schedule_id, payload)
                self.send_json(result); return
            if path.startswith("/api/workflows/") and path.endswith("/transition"):
                _, database = runtime()
                result = transition_workflow(database, path.split("/")[3], payload["state"])
                self.send_json(result); return
            if path == "/api/analytics/health":
                self.send_json(health_score(payload.get("signals", []))); return
            if path == "/api/analytics/cost-comparison":
                _, database = runtime()
                self.send_json(record_cost_comparison(database, payload), 201); return
            self.send_error(HTTPStatus.NOT_FOUND)
        except Exception as error:
            self.send_json({"error": str(error)}, 400)

    def do_DELETE(self) -> None:  # noqa: N802
        path = urlparse(self.path).path
        try:
            if path.startswith("/api/schedules/"):
                _, database = runtime()
                schedule_id = path.split("/")[3]
                ScheduleService(database).delete(schedule_id)
                self.send_json({"deleted": True, "id": schedule_id})
                return
            if path.startswith("/api/notifications/profiles/"):
                _, database = runtime()
                profile_id = path.split("/")[4]
                notifier(database).delete_profile(profile_id)
                self.send_json({"deleted": True, "id": profile_id})
                return
            self.send_error(HTTPStatus.NOT_FOUND)
        except Exception as error:
            self.send_json({"error": str(error)}, 400)


def main() -> None:
    settings, database = runtime()
    build_docs(ROOT, database)
    owner = f"ui-{uuid.uuid4()}"
    def scheduler_worker() -> None:
        service = ScheduleService(database)
        while True:
            try:
                fires = service.fire_due(owner, dispatcher=lambda workflow, key: {
                    "status": "waiting_approval" if workflow.get("action") == "evaluate_and_request_approval" else "planned",
                    "workflow_run_id": None,
                })
                for fire in fires:
                    if fire["state"] in {"skipped", "failed"}:
                        notifier(database).publish({
                            "topic": "schedule.misfire" if fire["state"] == "skipped" else "schedule.failed",
                            "severity": "warning", "resource_id": fire["schedule_id"],
                            "occurrence_key": fire["fire_key"],
                            "message": fire.get("error_summary") or f"Schedule fire {fire['state']}",
                        })
            except Exception:
                pass
            time.sleep(30)
    threading.Thread(target=scheduler_worker, daemon=True, name="emergegpt-scheduler").start()
    server = ThreadingHTTPServer((settings.bind_host, settings.port), Handler)
    print(f"EmergeGPT dashboard: http://{settings.bind_host}:{settings.port}")
    server.serve_forever()


if __name__ == "__main__":
    main()
