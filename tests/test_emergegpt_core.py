import json
import os
import tempfile
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path
from unittest.mock import patch

from emergegpt import approvals, costs, evaluations, health, product_scope, workflows
from emergegpt.db import Database
from emergegpt.decision_contracts import accept_suggestion, harness_suggestion, intent_contract, policy_decision
from emergegpt.evaluation_service import EvaluationService, validate_definition
from emergegpt.mcp_builder import create_draft, install, preview, update_draft, validate
from emergegpt.pipeline_runs import PipelineRunService, record_cost_comparison, student_profiles, teacher_profiles
from emergegpt.settings import Settings
from emergegpt.schedule_service import ScheduleService
from emergegpt.notification_service import NotificationService
from emergegpt.training import build_request


class EmergeGPTCoreTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.db = Database(Path(self.temp.name) / "test.db")
        self.db.migrate()

    def tearDown(self):
        self.temp.cleanup()

    def test_workflow_is_idempotent_and_transitions_are_guarded(self):
        one = workflows.create(self.db, "demo", {"model": "exact"}, "same-key")
        two = workflows.create(self.db, "demo", {"model": "exact"}, "same-key")
        self.assertEqual(one["id"], two["id"])
        with self.assertRaises(ValueError):
            workflows.transition(self.db, one["id"], "running")
        self.assertEqual("preflight", workflows.transition(self.db, one["id"], "preflight")["state"])

    def test_approval_is_exact_scope_and_one_time(self):
        scope = {"provider": "nebius", "mutation": "job_cancel", "job_id": "demo"}
        approval_id, nonce = approvals.issue(self.db, "wf", "tester", scope, "hash", 2.0)
        with self.assertRaises(PermissionError):
            approvals.consume(self.db, approval_id, nonce, workflow_id="wf", scope={**scope, "job_id": "other"}, config_hash="hash", estimated_cost=0)
        approvals.consume(self.db, approval_id, nonce, workflow_id="wf", scope=scope, config_hash="hash", estimated_cost=1)
        with self.assertRaises(PermissionError):
            approvals.consume(self.db, approval_id, nonce, workflow_id="wf", scope=scope, config_hash="hash", estimated_cost=1)

    def test_cost_and_health_math(self):
        self.assertAlmostEqual(costs.inference_cost(1_000_000, 1_000_000, .1, .3), .4)
        report = costs.comparison(base_tokens=100, tuned_tokens=80, base_cost=1, tuned_cost=.5, training_cost=10,
                                  evaluation_cost=0, deployment_setup_cost=0, expected_requests=100,
                                  base_successes=8, tuned_successes=9)
        self.assertEqual(20, report["token_savings_pct"])
        result = health.score([{"weight": 1, "severity": 1, "confidence": 1, "sample_count": 20, "minimum_samples": 10},
                               {"weight": 1, "severity": .8, "confidence": 1, "sample_count": 20, "minimum_samples": 10}])
        self.assertTrue(result["recommend_fine_tuning"])

    def test_wilson_interval_and_classification(self):
        low, high = evaluations.wilson_interval(80, 100)
        self.assertLess(low, .8); self.assertGreater(high, .8)
        self.assertEqual("passed", evaluations.classify(.95, warning=.8, target=.9, higher_is_better=True))

    def test_mcp_builder_is_diff_first_and_hash_guarded(self):
        draft = create_draft(self.db, "craft", {"credential_reference": "CRAFT_TOKEN"})
        plan = preview(self.db, draft["id"])
        self.assertFalse(plan["contains_secrets"])
        settings = self.safe_settings()
        self.assertTrue(validate(self.db, draft["id"], settings)["valid"])
        update_draft(self.db, draft["id"], "preview", {"mode": "stdio"})
        with self.assertRaises(ValueError):
            install(self.db, draft["id"], draft.get("config_hash", "old"))

    def safe_settings(self):
        env = {
            "EMERGEGPT_DB_PATH": str(Path(self.temp.name) / "settings.db"),
            "NEBIUS_PROJECT_ID": "replace-with-your-project-id",
            "CRAFT_CONNECTOR_ENABLED": "false",
        }
        with patch.dict(os.environ, env, clear=False):
            return Settings.load()

    def test_craft_connector_fails_closed(self):
        with patch.dict(os.environ, {"CRAFT_CONNECTOR_ENABLED": "true", "CRAFT_AUTHORIZATION_ATTESTED": "false"}, clear=False):
            with self.assertRaises(ValueError):
                Settings.load()

    def test_craft_readiness_requires_schema_and_probe(self):
        from emergegpt.providers.craft import CraftProvider
        env = {
            "CRAFT_CONNECTOR_ENABLED": "true", "CRAFT_AUTHORIZATION_ATTESTED": "true",
            "CRAFT_AUTHORIZATION_EXPIRES_AT": "2099-01-01T00:00:00Z",
            "CRAFT_TENANT_MCP_URL": "https://tenant.example.test/mcp", "CRAFT_PROJECT_ID": "project",
        }
        with patch.dict(os.environ, env, clear=False):
            status = CraftProvider(Settings.load()).authorization_status()
        self.assertFalse(status["read_ready"])
        self.assertFalse(status["gates"]["tool_schemas_discovered"])
        self.assertFalse(status["gates"]["harmless_read_probe_succeeded"])
        self.assertFalse(status["gates"]["mutations_separately_approved"])

    def test_product_scope_rejects_unrelated_work(self):
        key = "x" * 32
        manifest = product_scope.sign_manifest({
            "product_id": "emergegpt", "expires_at": "2099-01-01T00:00:00Z",
            "repositories": [self.temp.name], "path_allowlist": ["emergegpt/**"],
            "requirement_ids": ["MCP-001"], "operation_classes": ["connector"],
            "mcp_tools": ["craft_docs_search"], "network_allowlist": [],
        }, key)
        allowed = product_scope.authorize_run(
            manifest, key, repository=Path(self.temp.name), changed_paths=[Path("emergegpt/new.py")],
            requirement_id="MCP-001", operation_class="connector", mcp_tools=["craft_docs_search"],
        )
        self.assertTrue(allowed["authorized"])
        with self.assertRaises(PermissionError):
            product_scope.authorize_run(
                manifest, key, repository=Path(self.temp.name), changed_paths=[Path("unrelated/new.py")],
                requirement_id="MCP-001", operation_class="connector",
            )

    def test_pipeline_dispatch_is_persisted_and_idempotent(self):
        class FakeHarness:
            name = "fake"
            def capabilities(self): return {"name": "fake", "available": True}
            def run(self, request): return {"status": "succeeded", "request_id": request.request_id}

        settings = self.safe_settings()
        service = PipelineRunService(self.db, settings, {"fake": FakeHarness})
        payload = {
            "idempotency_key": "pipeline-once", "harness": "fake",
            "teacher_model": teacher_profiles(settings)[0]["model_id"],
            "student_model": "Qwen/Qwen3-30B-A3B-Instruct-2507",
            "dataset_path": "data/generated/digital-analytics-1000-teacher.jsonl",
            "stages": ["preflight", "prepare", "evaluate"], "live": False,
        }
        one = service.create(payload, background=False)
        two = service.create(payload, background=False)
        self.assertEqual(one["id"], two["id"])
        service._execute(one["id"])
        finished = service.get(one["id"])
        self.assertEqual("succeeded", finished["state"])
        self.assertEqual(4, len(finished["events"]))

    def test_teacher_and_student_catalogs_are_role_specific(self):
        settings = self.safe_settings()
        live = [{"id": "Qwen/Qwen3-32B", "context_length": 40960, "architecture": {"modality": "text->text"}},
                {"id": "Qwen/Qwen3-Embedding-8B", "architecture": {"modality": "text->embedding"}},
                {"id": "unknown/private-model", "context_length": 1000, "architecture": {"modality": "text->text"}}]
        teachers = teacher_profiles(settings, live)
        self.assertEqual(["Qwen/Qwen3-32B"], [item["model_id"] for item in teachers])
        students = {item["model_id"]: item for item in student_profiles()}
        self.assertIn("Qwen/Qwen3-30B-A3B-Instruct-2507", students)
        self.assertEqual(["full"], students["Qwen/Qwen3.5-27B"]["training_modes"])

    def test_live_pipeline_requires_exact_one_time_approval(self):
        class FakeHarness:
            name = "fake"
            def capabilities(self): return {"available": True}
            def run(self, request): return {"status": "succeeded"}

        settings = self.safe_settings()
        service = PipelineRunService(self.db, settings, {"fake": FakeHarness})
        payload = {
            "idempotency_key": "live-once", "harness": "fake",
            "teacher_model": teacher_profiles(settings)[0]["model_id"],
            "student_model": "Qwen/Qwen3-30B-A3B-Instruct-2507",
            "dataset_path": "data/generated/digital-analytics-1000-teacher.jsonl",
            "stages": ["generate", "submit", "monitor"], "live": True, "max_cost_usd": 2,
        }
        with self.assertRaises(PermissionError):
            service.create(payload, background=False)
        grant = service.issue_live_approval(payload)
        created = service.create({**payload, **grant}, background=False)
        self.assertEqual("queued", created["state"])
        with self.assertRaises(PermissionError):
            service.create({**payload, "idempotency_key": "replay", **grant}, background=False)

    def test_cost_savings_requires_matched_comparison(self):
        common = {"base_tokens": 100, "tuned_tokens": 80, "base_cost": 1, "tuned_cost": .5,
                  "training_cost": 10, "evaluation_cost": 0, "deployment_setup_cost": 0,
                  "expected_requests": 100, "base_successes": 8, "tuned_successes": 9}
        unmatched = record_cost_comparison(self.db, {**common, "base_comparison_key": "a", "tuned_comparison_key": "b"})
        self.assertFalse(unmatched["comparable"])
        matched = record_cost_comparison(self.db, {**common, "base_comparison_key": "a", "tuned_comparison_key": "a"})
        self.assertTrue(matched["comparable"])
        self.assertEqual(20, matched["token_savings_pct"])

    def test_schedule_lifecycle_and_fire_history(self):
        service = ScheduleService(self.db)
        schedule = service.create({"name": "Evaluate", "expression": "0 9 * * 1",
                                   "timezone": "America/New_York",
                                   "workflow": {"action": "evaluate_and_request_approval"}})
        self.assertTrue(schedule["enabled"])
        paused = service.set_enabled(schedule["id"], False)
        self.assertFalse(paused["enabled"])
        resumed = service.set_enabled(schedule["id"], True)
        self.assertTrue(resumed["enabled"])
        updated = service.update(schedule["id"], {"name": "Weekly evaluation"})
        self.assertEqual("Weekly evaluation", updated["name"])
        fired = service.run_now(schedule["id"], lambda workflow, key: {"status": "waiting_approval"})
        self.assertEqual("waiting_approval", fired["state"])
        self.assertEqual(1, len(service.get(schedule["id"])["fires"]))
        service.delete(schedule["id"])
        with self.assertRaises(KeyError):
            service.get(schedule["id"])

    def test_scheduler_lease_has_single_owner(self):
        service = ScheduleService(self.db)
        now = datetime.now(timezone.utc)
        self.assertTrue(service.acquire_lease("one", now, ttl_seconds=60))
        self.assertFalse(service.acquire_lease("two", now, ttl_seconds=60))

    def test_scheduler_misfire_skip_is_recorded_and_not_dispatched(self):
        service = ScheduleService(self.db)
        schedule = service.create({"name": "Skip late", "expression": "* * * * *", "timezone": "UTC",
                                   "workflow": {"action": "evaluate_and_request_approval",
                                                "schedule_policy": {"misfire": "skip", "max_concurrency": 1}}})
        now = datetime.now(timezone.utc)
        with self.db.connect() as connection:
            connection.execute("UPDATE schedules SET next_fire_at=? WHERE id=?",
                               ((now - timedelta(minutes=5)).isoformat(), schedule["id"]))
        dispatched = []
        fires = service.fire_due("worker", lambda workflow, key: dispatched.append(key), now=now)
        self.assertEqual([], dispatched)
        self.assertEqual("skipped", fires[0]["state"])
        self.assertIn("misfire", fires[0]["error_summary"])

    def test_notification_subscription_severity_and_deduplication(self):
        sent = []
        class FakeAdapter:
            def __init__(self, config): self.config = config
            def send(self, notification): sent.append(notification); return {"status": "sent"}
        service = NotificationService(self.db, {"email": FakeAdapter})
        profile = service.create_profile({"name": "Owner", "channel": "email",
                                          "config": {"recipient": "owner@example.test"}})
        service.subscribe(profile["id"], "security.violation", "warning")
        event = {"topic": "security.violation", "severity": "info", "resource_id": "run-1",
                 "occurrence_key": "one", "message": "Policy violation"}
        result = service.publish(event, {"severity": "info", "rationale": "Harness considered it low"})
        self.assertEqual("critical", result["severity"])
        self.assertEqual(1, len(sent))
        duplicate = service.publish(event)
        self.assertTrue(duplicate["deduplicated"])
        self.assertEqual(1, len(sent))

    def test_notification_secret_profiles_store_references_not_values(self):
        service = NotificationService(self.db)
        profile = service.create_profile({"name": "Slack", "channel": "slack",
                                          "config": {"webhook_env": "EMERGEGPT_SLACK_WEBHOOK_URL"}})
        self.assertEqual("EMERGEGPT_SLACK_WEBHOOK_URL", profile["config"]["webhook_env"])
        with self.assertRaises(ValueError):
            service.create_profile({"name": "Bad", "channel": "slack",
                                    "config": {"webhook_env": "https://secret.example"}})

    def test_notification_alert_can_be_acknowledged_and_resolved(self):
        service = NotificationService(self.db)
        alert_id = service.publish({"topic": "budget.exceeded", "resource_id": "job-1",
                                    "occurrence_key": "limit", "message": "Limit reached"})["alert_id"]
        self.assertEqual("acknowledged", service.set_alert_state(alert_id, "acknowledged")["state"])
        self.assertEqual("resolved", service.set_alert_state(alert_id, "resolved")["state"])
        with self.assertRaises(ValueError):
            service.set_alert_state(alert_id, "hidden")

    def test_evaluation_registry_recommendation_and_safe_plan(self):
        service = EvaluationService(self.db)
        self.assertGreaterEqual(service.sync_builtins(), 3)
        identifiers = {item["id"] for item in service.list_definitions()}
        self.assertTrue({"mmlu", "arc-challenge", "arc-agi"}.issubset(identifiers))
        advice = service.recommend({"domains": ["data_catalog", "general"], "model": "student",
                                    "full_supported": True, "behavioral_shift": "bounded"})
        recommendations = advice["suggestion"]["recommendations"]
        self.assertIn({"evaluation_id": "mmlu"}, recommendations)
        self.assertEqual("lora", recommendations[-1]["training_mode"])
        run = service.create_run({"definition_id": "mmlu", "model_id": "student",
                                  "parameters": {"limit": 10}}, background=False)
        definition = next(item for item in service.list_definitions() if item["id"] == "mmlu")
        service._execute(run["id"], definition, {"model_id": "student", "parameters": {"limit": 10}}, None)
        planned = service.get_run(run["id"])
        self.assertEqual("planned", planned["state"])
        self.assertEqual("lm-eval", planned["result"]["planned_command"]["runner"])
        readiness = service.promotion_readiness("student")
        self.assertFalse(readiness["ready"])
        self.assertEqual("promotion_blocked", readiness["decision"])

    def test_evaluation_runner_allowlist_and_harness_authority_boundary(self):
        with self.assertRaises(ValueError):
            validate_definition({"id": "unsafe", "version": 1, "description": "unsafe",
                                 "runner": "shell", "metrics": [{"name": "x"}],
                                 "required_for_promotion": False})
        intent = intent_contract({"actor": "owner", "objective": "evaluate", "operation_classes": ["evaluation.execute"],
                                  "budgets": {"max_cost_usd": 1}, "approval_policy": "explicit"})
        suggestion = harness_suggestion(intent, {"recommendations": [], "confidence": .8,
                                                "rationale": "domain match", "evidence_citations": [], "assumptions": []})
        self.assertEqual("denied", policy_decision(intent, suggestion, {"evaluation.advice"})["decision"])
        accepted = accept_suggestion(intent, suggestion, [])
        self.assertNotEqual(intent["intent_hash"], accepted["intent_hash"])

    def test_full_training_omits_lora_only_fields(self):
        request = build_request(exact_model="exact", training_file="train", validation_file=None,
                                training_mode="full", hyperparameters={"batch_size": 8, "lora_r": 16, "lora_alpha": 16},
                                capabilities={"full_supported": True}, seed=42, suffix="demo")
        self.assertFalse(request["hyperparameters"]["lora"])
        self.assertNotIn("lora_r", request["hyperparameters"])

    def test_unsupported_training_mode_is_blocked(self):
        with self.assertRaises(ValueError):
            build_request(exact_model="exact", training_file="train", validation_file=None,
                          training_mode="full", hyperparameters={}, capabilities={"full_supported": False},
                          seed=42, suffix="demo")


if __name__ == "__main__":
    unittest.main()
