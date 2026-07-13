"""Evaluation definition registry, safe imports, harness advice, and run plans."""

from __future__ import annotations

import json
import threading
import uuid
from datetime import datetime, timedelta, timezone
from pathlib import Path

from .db import Database
from .decision_contracts import canonical_hash, harness_suggestion, intent_contract
from .harnesses.base import HarnessRequest
from .settings import ROOT

RUNNERS = {"builtin", "prompt-cases", "pairwise", "provider-usage", "lm-eval", "arc-agi", "custom-sandbox"}
DOMAIN_RECOMMENDATIONS = {
    "data_catalog": ["dataset-integrity", "evidence-grounding", "tool-use", "privacy-policy", "latency-cost"],
    "workflow": ["tool-use", "privacy-policy", "pairwise-base-candidate", "latency-cost"],
    "agent_registry": ["tool-use", "evidence-grounding", "privacy-policy", "pairwise-base-candidate"],
    "general": ["mmlu", "arc-challenge"], "abstract_reasoning": ["arc-agi"],
}


class EvaluationService:
    def __init__(self, db: Database, harnesses: dict | None = None):
        self.db, self.harnesses = db, harnesses or {}

    def sync_builtins(self) -> int:
        count = 0
        for path in sorted((ROOT / "evals" / "definitions").glob("*.json")):
            self.upsert_definition(json.loads(path.read_text()), origin={"kind": "builtin", "path": str(path.relative_to(ROOT))})
            count += 1
        return count

    def upsert_definition(self, definition: dict, origin: dict | None = None) -> dict:
        normalized = validate_definition(definition)
        stored = {**normalized, "origin": origin or {"kind": "user"}}
        with self.db.connect() as connection:
            connection.execute("INSERT INTO evaluation_definitions VALUES (?,?,?) ON CONFLICT(id,version) DO UPDATE SET definition_json=excluded.definition_json",
                               (stored["id"], stored["version"], json.dumps(stored, sort_keys=True)))
        return stored

    def list_definitions(self) -> list[dict]:
        with self.db.connect() as connection:
            rows = connection.execute("SELECT definition_json FROM evaluation_definitions ORDER BY id,version DESC").fetchall()
        return [json.loads(row[0]) for row in rows]

    def recommend(self, payload: dict, harness_factory=None) -> dict:
        domains = sorted(set(payload.get("domains", []))) or ["general"]
        eval_ids = []
        for domain in domains:
            eval_ids.extend(DOMAIN_RECOMMENDATIONS.get(domain, []))
        eval_ids = list(dict.fromkeys(eval_ids))
        mode = _training_mode_advice(payload)
        intent = intent_contract({"actor": payload.get("actor", "local-user"),
                                  "objective": "recommend evaluations and training mode",
                                  "operation_classes": ["evaluation.advice"],
                                  "budgets": {"max_cost_usd": payload.get("max_cost_usd", 0)},
                                  "approval_policy": "suggestion_only",
                                  "assets": payload.get("assets", []), "domains": domains,
                                  "model": payload.get("model")})
        proposal = {"recommendations": [{"evaluation_id": item} for item in eval_ids] + [mode],
                    "confidence": 0.7, "rationale": "Deterministic baseline derived from selected catalog domains and model capability inputs.",
                    "evidence_citations": payload.get("evidence_citations", []),
                    "assumptions": ["Evaluation selection is independent of LoRA versus full training."]}
        if harness_factory:
            harness = harness_factory()
            request = HarnessRequest(str(uuid.uuid4()), ROOT,
                                     "Review this EmergeGPT evaluation recommendation. Return JSON with recommendations, confidence, rationale, evidence_citations, and assumptions. Do not execute evaluations or change policy.\n" + json.dumps({"intent": intent, "baseline": proposal}, sort_keys=True),
                                     timeout_seconds=120)
            raw = harness.run(request)
            candidate = raw.get("result", raw)
            if all(key in candidate for key in ("recommendations", "confidence", "rationale", "evidence_citations", "assumptions")):
                proposal = candidate
        suggestion = harness_suggestion(intent, proposal)
        suggestion_id, now = str(uuid.uuid4()), _now()
        expires = (datetime.now(timezone.utc) + timedelta(hours=24)).isoformat()
        with self.db.connect() as connection:
            connection.execute("INSERT INTO evaluation_suggestions VALUES (?,?,?,?,?,?,NULL)",
                               (suggestion_id, intent["intent_hash"], payload.get("harness"), json.dumps(suggestion, sort_keys=True), now, expires))
        return {"id": suggestion_id, "intent": intent, "suggestion": suggestion, "expires_at": expires}

    def create_run(self, payload: dict, harness_factory=None, background: bool = True) -> dict:
        definition = self._definition(payload["definition_id"], payload.get("version"))
        parameters = {**definition.get("parameters", {}), **payload.get("parameters", {})}
        run_id, now = str(uuid.uuid4()), _now()
        config = {"definition": {"id": definition["id"], "version": definition["version"]},
                  "model_id": payload["model_id"], "comparison_model_id": payload.get("comparison_model_id"),
                  "parameters": parameters, "harness": payload.get("harness")}
        with self.db.connect() as connection:
            connection.execute("INSERT INTO evaluation_runs VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
                               (run_id, definition["id"], definition["version"], payload["model_id"],
                                payload.get("comparison_model_id"), "queued", json.dumps(parameters, sort_keys=True),
                                payload.get("harness"), canonical_hash(config), now, None, None, "{}", None))
        if background:
            threading.Thread(target=self._execute, args=(run_id, definition, config, harness_factory), daemon=True).start()
        return self.get_run(run_id)

    def get_run(self, run_id: str) -> dict:
        with self.db.connect() as connection:
            row = connection.execute("SELECT * FROM evaluation_runs WHERE id=?", (run_id,)).fetchone()
            if not row: raise KeyError("evaluation run not found")
        result = dict(row); result["parameters"] = json.loads(result.pop("parameters_json")); result["result"] = json.loads(result.pop("result_json"))
        return result

    def list_runs(self) -> list[dict]:
        with self.db.connect() as connection:
            ids = [row[0] for row in connection.execute("SELECT id FROM evaluation_runs ORDER BY created_at DESC LIMIT 50")]
        return [self.get_run(item) for item in ids]

    def promotion_readiness(self, model_id: str) -> dict:
        required = [item for item in self.list_definitions() if item.get("required_for_promotion")]
        runs = self.list_runs()
        evidence, missing, failed = [], [], []
        for definition in required:
            candidates = [run for run in runs if run["model_id"] == model_id and
                          run["definition_id"] == definition["id"] and
                          run["definition_version"] == definition["version"]]
            latest = candidates[0] if candidates else None
            if not latest or latest["state"] not in {"succeeded", "passed"}:
                (failed if latest and latest["state"] == "failed" else missing).append(definition["id"])
            if latest: evidence.append({"definition_id": definition["id"], "run_id": latest["id"], "state": latest["state"]})
        return {"model_id": model_id, "ready": not missing and not failed,
                "decision": "promotion_allowed" if not missing and not failed else "promotion_blocked",
                "missing": missing, "failed": failed, "evidence": evidence}

    def _execute(self, run_id: str, definition: dict, config: dict, harness_factory) -> None:
        with self.db.connect() as connection:
            connection.execute("UPDATE evaluation_runs SET state='running',started_at=? WHERE id=?", (_now(), run_id))
        try:
            command = runner_command(definition, config["model_id"], config["parameters"])
            if harness_factory:
                harness = harness_factory()
                result = harness.run(HarnessRequest(run_id, ROOT,
                    "Execute or supervise only this allowlisted evaluation command and return structured result JSON. Do not modify models or training configuration.\n" + json.dumps(command), timeout_seconds=600))
                state = "succeeded"
            else:
                result, state = {"planned_command": command, "notice": "No harness selected; no evaluation executed."}, "planned"
            error = None
        except Exception as exc:
            result, state, error = {}, "failed", str(exc)[-500:]
        with self.db.connect() as connection:
            connection.execute("UPDATE evaluation_runs SET state=?,finished_at=?,result_json=?,error_summary=? WHERE id=?",
                               (state, _now(), json.dumps(result, sort_keys=True), error, run_id))

    def _definition(self, definition_id: str, version: int | None) -> dict:
        with self.db.connect() as connection:
            row = connection.execute("SELECT definition_json FROM evaluation_definitions WHERE id=? " +
                                     ("AND version=?" if version else "ORDER BY version DESC LIMIT 1"),
                                     ((definition_id, version) if version else (definition_id,))).fetchone()
        if not row: raise KeyError("evaluation definition not found")
        return json.loads(row[0])


def validate_definition(value: dict) -> dict:
    required = {"id", "version", "description", "runner", "metrics", "required_for_promotion"}
    missing = required - set(value)
    if missing: raise ValueError("evaluation definition missing: " + ", ".join(sorted(missing)))
    if value["runner"] not in RUNNERS: raise ValueError("evaluation runner is not allowlisted")
    if not isinstance(value["metrics"], list) or not value["metrics"]: raise ValueError("evaluation requires metrics")
    return value


def runner_command(definition: dict, model_id: str, parameters: dict) -> dict:
    runner = definition["runner"]
    if runner == "lm-eval":
        return {"argv": ["lm_eval", "--model", "hf", "--model_args", f"pretrained={model_id}",
                         "--tasks", definition["task"], "--limit", str(parameters.get("limit", 100))], "runner": runner}
    if runner == "arc-agi":
        return {"runner": runner, "task": definition["task"], "parameters": parameters,
                "sandbox_required": True, "network": "denied"}
    return {"runner": runner, "definition_id": definition["id"], "parameters": parameters}


def _training_mode_advice(payload: dict) -> dict:
    full = bool(payload.get("full_supported")); shift = payload.get("behavioral_shift", "bounded")
    if full and shift == "foundation-wide":
        return {"training_mode": "full", "reason": "Foundation-wide change requested and the exact model supports full fine-tuning."}
    return {"training_mode": "lora", "reason": "Prefer the lower-cost, reversible mode for bounded behavior changes; evaluations apply to either mode."}


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()
