"""Persisted, harness-dispatched EmergeGPT pipeline execution requests."""

from __future__ import annotations

import json
import threading
import uuid
from datetime import datetime, timezone
from pathlib import Path

from .db import Database
from . import approvals
from .harnesses.adapters import ALL_HARNESSES
from .harnesses.base import HarnessRequest
from .settings import ROOT, Settings
from .workflows import canonical_hash
from .costs import comparison as calculate_cost_comparison

ALLOWED_STAGES = {"preflight", "generate", "prepare", "submit", "monitor", "evaluate"}
LIVE_STAGES = {"generate", "submit", "monitor"}
TERMINAL = {"succeeded", "failed", "cancelled", "timed_out"}


def _model_capabilities() -> dict:
    return json.loads((ROOT / "config" / "nebius-model-capabilities.json").read_text())


def teacher_profiles(settings: Settings, live_models: list[dict] | None = None) -> list[dict]:
    registry = _model_capabilities()
    profiles = []
    for model in live_models or []:
        model_id = model.get("id")
        license_name = registry["license_evidence"].get(model_id)
        modality = str(model.get("architecture", {}).get("modality", ""))
        if not model_id or not license_name or not modality.endswith("->text"):
            continue
        profiles.append({
            "provider": "nebius", "model_id": model_id, "license": license_name,
            "open_weights": True, "inference_eligible": True,
            "context_length": model.get("context_length"), "pricing": model.get("pricing"),
            "source": "live_nebius_catalog+license_registry", "roles": ["teacher"],
        })
    if not live_models:
        configured = json.loads((ROOT / "config" / "pipeline.json").read_text())["student"]
        profiles.append({"provider": "nebius", "model_id": configured["model"], "license": configured["license"],
                         "open_weights": True, "inference_eligible": True, "source": "configured_verified_profile",
                         "roles": ["teacher"]})
    unique = {item["model_id"]: item for item in profiles}
    return sorted(unique.values(), key=lambda item: item["model_id"])


def student_profiles() -> list[dict]:
    registry = _model_capabilities()
    return [{"provider": "nebius", "model_id": item["id"], "license": item["license"],
             "training_modes": item["modes"], "fine_tuning_eligible": True,
             "source": registry["fine_tuning_source"], "verified_at": registry["verified_at"]}
            for item in registry["fine_tunable_models"]]


def record_cost_comparison(db: Database, payload: dict) -> dict:
    comparable = bool(payload.get("base_comparison_key")) and payload.get("base_comparison_key") == payload.get("tuned_comparison_key")
    result = {"comparable": comparable}
    if comparable:
        fields = ("base_tokens", "tuned_tokens", "base_cost", "tuned_cost", "training_cost",
                  "evaluation_cost", "deployment_setup_cost", "expected_requests", "base_successes", "tuned_successes")
        values = {field: float(payload.get(field, 0)) for field in fields}
        values["expected_requests"] = int(values["expected_requests"])
        values["base_successes"] = int(values["base_successes"])
        values["tuned_successes"] = int(values["tuned_successes"])
        result.update(calculate_cost_comparison(**values))
    else:
        result["reason"] = "Base and tuned runs must use the same prompts, settings, and evaluation profile."
    comparison_id, now = str(uuid.uuid4()), _now()
    with db.connect() as connection:
        connection.execute("INSERT INTO cost_comparisons VALUES (?,?,?,?,?)",
                           (comparison_id, now, int(comparable), json.dumps(payload, sort_keys=True), json.dumps(result, sort_keys=True)))
    return {"id": comparison_id, "created_at": now, **result}


class PipelineRunService:
    def __init__(self, db: Database, settings: Settings, harnesses: dict | None = None, notifier=None):
        self.db, self.settings = db, settings
        self.harnesses = harnesses or ALL_HARNESSES
        self.notifier = notifier

    def create(self, payload: dict, *, background: bool = True) -> dict:
        request = self._validate(payload)
        now, run_id = _now(), str(uuid.uuid4())
        request_hash = canonical_hash(request)
        if request["live"]:
            approvals.consume(
                self.db, payload.get("approval_id", ""), payload.get("approval_nonce", ""),
                workflow_id=f"pipeline:{request['idempotency_key']}", scope=_approval_scope(request),
                config_hash=request_hash, estimated_cost=request["max_cost_usd"],
            )
        with self.db.connect() as connection:
            existing = connection.execute("SELECT id FROM pipeline_runs WHERE idempotency_key=?", (request["idempotency_key"],)).fetchone()
            if existing:
                return self.get(existing["id"])
            connection.execute(
                "INSERT INTO pipeline_runs VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
                (run_id, request["idempotency_key"], "queued", "request", 0.0,
                 json.dumps(request, sort_keys=True), request_hash, request["harness"],
                 request["teacher_model"], request["student_model"], None, None,
                 now, now, None),
            )
        self._event(run_id, "queued", "request", 0, "Pipeline request accepted", {"request_hash": request_hash})
        self._notify("pipeline.started", "info", run_id, f"Pipeline {run_id} was queued through {request['harness']}.")
        if background:
            threading.Thread(target=self._execute, args=(run_id,), daemon=True, name=f"pipeline-{run_id[:8]}").start()
        return self.get(run_id)

    def issue_live_approval(self, payload: dict, actor: str = "local-user") -> dict:
        request = self._validate({**payload, "live": True})
        request_hash = canonical_hash(request)
        approval_id, nonce = approvals.issue(
            self.db, f"pipeline:{request['idempotency_key']}", actor,
            _approval_scope(request), request_hash, request["max_cost_usd"], ttl_seconds=900,
        )
        return {"approval_id": approval_id, "approval_nonce": nonce, "request_hash": request_hash,
                "expires_in_minutes": 15, "scope": _approval_scope(request)}

    def _validate(self, payload: dict) -> dict:
        required = ("idempotency_key", "harness", "teacher_model", "student_model", "dataset_path")
        missing = [key for key in required if not str(payload.get(key, "")).strip()]
        if missing:
            raise ValueError("missing pipeline fields: " + ", ".join(missing))
        if payload["harness"] not in self.harnesses:
            raise ValueError("selected harness is not supported")
        stages = list(dict.fromkeys(payload.get("stages") or ["preflight", "generate", "prepare", "evaluate"]))
        if set(stages) - ALLOWED_STAGES:
            raise ValueError("pipeline contains an unsupported stage")
        live = bool(payload.get("live"))
        # Dry runs may plan live-capable stages, but the harness prompt explicitly
        # forbids executing provider mutations. Actual live execution consumes a
        # separate exact-scope approval in create().
        eligible = set(_model_capabilities()["license_evidence"])
        if payload["teacher_model"] not in eligible:
            raise ValueError("teacher model lacks recorded open-weight license and inference eligibility")
        students = {item["model_id"]: item for item in student_profiles()}
        if payload["student_model"] not in students:
            raise ValueError("student model is not on the current Nebius fine-tuning allowlist")
        if payload.get("training_mode", "lora") not in students[payload["student_model"]]["training_modes"]:
            raise ValueError("selected training mode is not supported for this student model")
        dataset = (ROOT / payload["dataset_path"]).resolve(strict=True)
        if ROOT != dataset and ROOT not in dataset.parents:
            raise ValueError("dataset must be inside the EmergeGPT workspace")
        if not dataset.is_file():
            raise ValueError("dataset_path must identify a reviewed input file")
        return {
            "idempotency_key": str(payload["idempotency_key"]), "harness": payload["harness"],
            "teacher_model": payload["teacher_model"], "student_model": payload["student_model"],
            "dataset_path": dataset.relative_to(ROOT).as_posix(), "dataset_sha256": _sha256(dataset),
            "training_mode": payload.get("training_mode", "lora"), "stages": stages, "live": live,
            "max_seconds": min(max(int(payload.get("max_seconds", 900)), 30), 3600),
            "max_cost_usd": max(float(payload.get("max_cost_usd", 0)), 0),
            "evaluation_profile": payload.get("evaluation_profile", "required-default"),
            "seed_path": payload.get("seed_path", "data/seeds/digital-analytics-1000.jsonl"),
            "catalog_path": payload.get("catalog_path", "data/generated/digital-analytics-catalogs.json"),
            "teacher_output_path": payload.get("teacher_output_path", "data/generated/ui-nebius-teacher.jsonl"),
        }

    def _execute(self, run_id: str) -> None:
        run = self.get(run_id)
        request = run["request"]
        try:
            harness = self.harnesses[request["harness"]]()
            capabilities = harness.capabilities()
            if not capabilities.get("available"):
                raise RuntimeError(f"{request['harness']} harness is not installed or configured")
            self._transition(run_id, "dispatching", "harness", 10, "Notifying selected model harness", {"capabilities": capabilities})
            prompt = _execution_prompt(run_id, run["request_hash"], request)
            self._transition(run_id, "running", "harness", 25, "Harness accepted the bounded execution request", {})
            result = harness.run(HarnessRequest(
                request_id=run_id, workspace=ROOT, prompt=prompt,
                timeout_seconds=request["max_seconds"],
            ))
            self._transition(run_id, "succeeded", "complete", 100, "Harness completed the pipeline request", {"harness_result": result})
            self._notify("pipeline.completed", "info", run_id, f"Pipeline {run_id} completed successfully.")
        except Exception as error:
            summary = str(error).replace("\n", " ")[-500:]
            self._transition(run_id, "failed", "harness", 100, "Pipeline dispatch failed", {"error": summary}, error_summary=summary)
            self._notify("pipeline.failed", "warning", run_id, f"Pipeline {run_id} failed: {summary}")

    def get(self, run_id: str) -> dict:
        with self.db.connect() as connection:
            row = connection.execute("SELECT * FROM pipeline_runs WHERE id=?", (run_id,)).fetchone()
            if not row:
                raise KeyError("pipeline run not found")
            events = [dict(item) for item in connection.execute(
                "SELECT sequence,occurred_at,state,stage,progress,message,details_json FROM pipeline_events WHERE run_id=? ORDER BY sequence", (run_id,)
            )]
        result = dict(row)
        result["request"] = json.loads(result.pop("request_json"))
        for event in events:
            encoded = event.pop("details_json")
            try:
                event["details"] = json.loads(encoded)
            except json.JSONDecodeError:
                event["details"] = {"redacted": True, "reason": "legacy event exceeded the bounded event envelope"}
        result["events"] = events
        return result

    def list(self) -> list[dict]:
        with self.db.connect() as connection:
            ids = [row[0] for row in connection.execute("SELECT id FROM pipeline_runs ORDER BY created_at DESC LIMIT 50")]
        return [self.get(run_id) for run_id in ids]

    def _event(self, run_id: str, state: str, stage: str, progress: float, message: str, details: dict) -> None:
        with self.db.connect() as connection:
            sequence = connection.execute("SELECT COALESCE(MAX(sequence),0)+1 FROM pipeline_events WHERE run_id=?", (run_id,)).fetchone()[0]
            connection.execute("INSERT INTO pipeline_events(run_id,sequence,occurred_at,state,stage,progress,message,details_json) VALUES (?,?,?,?,?,?,?,?)",
                               (run_id, sequence, _now(), state, stage, progress, message[:500], _bounded_json(details)))

    def _transition(self, run_id: str, state: str, stage: str, progress: float, message: str, details: dict, error_summary: str | None = None) -> None:
        now = _now()
        with self.db.connect() as connection:
            connection.execute("UPDATE pipeline_runs SET state=?,stage=?,progress=?,updated_at=?,finished_at=?,error_summary=? WHERE id=?",
                               (state, stage, progress, now, now if state in TERMINAL else None, error_summary, run_id))
        self._event(run_id, state, stage, progress, message, details)

    def _notify(self, topic: str, severity: str, resource_id: str, message: str) -> None:
        if self.notifier:
            self.notifier.publish({"topic": topic, "severity": severity, "resource_id": resource_id,
                                   "occurrence_key": f"{resource_id}:{topic}", "message": message})


def _execution_prompt(run_id: str, request_hash: str, request: dict) -> str:
    mode = "execute the allowlisted stages" if request["live"] else "produce and validate a dry-run plan; perform no provider mutation"
    teacher_command = (
        "python3 scripts/pipeline.py generate --teacher-provider nebius "
        f"--teacher-model {request['teacher_model']} --seeds {request['seed_path']} "
        f"--catalog {request['catalog_path']} --output {request['teacher_output_path']}"
    )
    return (
        "You are the selected EmergeGPT model harness. Handle only this immutable pipeline request. "
        f"Run ID: {run_id}. Request hash: {request_hash}. You must {mode}. "
        "Use scripts/pipeline.py and existing project policy. Do not change exact models, dataset, mode, limits, or stages; "
        "do not expose secrets or hidden chain-of-thought. For the generate stage, use this exact provider-aware command: "
        f"{teacher_command}. Return structured JSON summarizing planned/executed commands, stage status, and artifacts.\n"
        + json.dumps(request, sort_keys=True)
    )


def _approval_scope(request: dict) -> dict:
    return {key: request[key] for key in (
        "harness", "teacher_model", "student_model", "dataset_sha256", "training_mode", "stages", "max_seconds"
    )} | {"action": "pipeline_live"}


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _sha256(path: Path) -> str:
    digest = __import__("hashlib").sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _bounded_json(details: dict, limit: int = 10000) -> str:
    encoded = json.dumps(details, sort_keys=True)
    if len(encoded) <= limit:
        return encoded
    return json.dumps({"redacted": True, "reason": "event details exceeded bounded envelope",
                       "sha256": __import__("hashlib").sha256(encoded.encode()).hexdigest(),
                       "original_characters": len(encoded)}, sort_keys=True)
