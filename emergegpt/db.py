"""SQLite operational store and migrations."""

from __future__ import annotations

import sqlite3
from contextlib import contextmanager
from pathlib import Path

MIGRATIONS = [
    """
    CREATE TABLE IF NOT EXISTS schema_migrations(version INTEGER PRIMARY KEY, applied_at TEXT NOT NULL);
    CREATE TABLE IF NOT EXISTS audit_events(
      id TEXT PRIMARY KEY, occurred_at TEXT NOT NULL, actor TEXT NOT NULL, action TEXT NOT NULL,
      resource_type TEXT NOT NULL, resource_id TEXT, outcome TEXT NOT NULL, trace_id TEXT, details_json TEXT NOT NULL
    );
    CREATE TABLE IF NOT EXISTS connector_authorizations(
      id TEXT PRIMARY KEY, provider TEXT NOT NULL, basis TEXT NOT NULL, effective_at TEXT NOT NULL,
      expires_at TEXT NOT NULL, actor TEXT NOT NULL, scopes_json TEXT NOT NULL, status TEXT NOT NULL,
      evidence_reference TEXT
    );
    CREATE TABLE IF NOT EXISTS workflow_runs(
      id TEXT PRIMARY KEY, definition_id TEXT NOT NULL, state TEXT NOT NULL, config_hash TEXT NOT NULL,
      idempotency_key TEXT UNIQUE NOT NULL, created_at TEXT NOT NULL, updated_at TEXT NOT NULL, details_json TEXT NOT NULL
    );
    CREATE TABLE IF NOT EXISTS approvals(
      id TEXT PRIMARY KEY, workflow_id TEXT NOT NULL, actor TEXT NOT NULL, scope_json TEXT NOT NULL,
      config_hash TEXT NOT NULL, max_cost REAL NOT NULL, nonce_hash TEXT UNIQUE NOT NULL,
      expires_at TEXT NOT NULL, consumed_at TEXT
    );
    CREATE TABLE IF NOT EXISTS schedules(
      id TEXT PRIMARY KEY, name TEXT NOT NULL, expression TEXT NOT NULL, timezone TEXT NOT NULL,
      workflow_json TEXT NOT NULL, enabled INTEGER NOT NULL, next_fire_at TEXT, created_at TEXT NOT NULL
    );
    CREATE TABLE IF NOT EXISTS evaluation_definitions(
      id TEXT NOT NULL, version INTEGER NOT NULL, definition_json TEXT NOT NULL, PRIMARY KEY(id, version)
    );
    CREATE TABLE IF NOT EXISTS metric_results(
      id TEXT PRIMARY KEY, evaluation_run_id TEXT NOT NULL, metric_id TEXT NOT NULL,
      value REAL, status TEXT NOT NULL, result_json TEXT NOT NULL
    );
    CREATE TABLE IF NOT EXISTS usage_events(
      id TEXT PRIMARY KEY, occurred_at TEXT NOT NULL, model TEXT NOT NULL, variant TEXT NOT NULL,
      prompt_id TEXT, input_tokens INTEGER NOT NULL, output_tokens INTEGER NOT NULL,
      input_price REAL NOT NULL, output_price REAL NOT NULL, billed_cost REAL, metadata_json TEXT NOT NULL
    );
    CREATE TABLE IF NOT EXISTS health_snapshots(
      id TEXT PRIMARY KEY, occurred_at TEXT NOT NULL, risk REAL NOT NULL, band TEXT NOT NULL, signals_json TEXT NOT NULL
    );
    CREATE TABLE IF NOT EXISTS alerts(
      id TEXT PRIMARY KEY, fingerprint TEXT UNIQUE NOT NULL, severity TEXT NOT NULL, state TEXT NOT NULL,
      created_at TEXT NOT NULL, updated_at TEXT NOT NULL, details_json TEXT NOT NULL
    );
    CREATE TABLE IF NOT EXISTS mcp_drafts(
      id TEXT PRIMARY KEY, server_kind TEXT NOT NULL, step TEXT NOT NULL, config_json TEXT NOT NULL,
      config_hash TEXT NOT NULL, created_at TEXT NOT NULL, updated_at TEXT NOT NULL
    );
    CREATE TABLE IF NOT EXISTS mcp_installations(
      id TEXT PRIMARY KEY, draft_id TEXT NOT NULL, server_kind TEXT NOT NULL, status TEXT NOT NULL,
      manifest_hash TEXT NOT NULL, backup_path TEXT, installed_at TEXT NOT NULL, details_json TEXT NOT NULL
    );
    CREATE TABLE IF NOT EXISTS documentation_sources(
      path TEXT PRIMARY KEY, sha256 TEXT NOT NULL, title TEXT NOT NULL, verified_at TEXT, content TEXT NOT NULL
    );
    """,
    """
    CREATE TABLE IF NOT EXISTS models(
      id TEXT PRIMARY KEY, provider TEXT NOT NULL, provider_model_id TEXT NOT NULL,
      license TEXT, open_weights INTEGER NOT NULL, roles_json TEXT NOT NULL, metadata_json TEXT NOT NULL
    );
    CREATE TABLE IF NOT EXISTS model_capabilities(
      model_id TEXT NOT NULL, observed_at TEXT NOT NULL, inference_supported INTEGER NOT NULL,
      lora_supported INTEGER NOT NULL, full_supported INTEGER NOT NULL, deploy_supported INTEGER NOT NULL,
      evidence_json TEXT NOT NULL, PRIMARY KEY(model_id, observed_at)
    );
    CREATE TABLE IF NOT EXISTS workflow_steps(
      id TEXT PRIMARY KEY, workflow_id TEXT NOT NULL, name TEXT NOT NULL, state TEXT NOT NULL,
      started_at TEXT, finished_at TEXT, details_json TEXT NOT NULL
    );
    CREATE TABLE IF NOT EXISTS notification_deliveries(
      id TEXT PRIMARY KEY, alert_id TEXT NOT NULL, channel TEXT NOT NULL, attempt INTEGER NOT NULL,
      status TEXT NOT NULL, occurred_at TEXT NOT NULL, response_class TEXT
    );
    CREATE TABLE IF NOT EXISTS documentation_builds(
      id TEXT PRIMARY KEY, build_hash TEXT UNIQUE NOT NULL, source_count INTEGER NOT NULL,
      created_at TEXT NOT NULL, details_json TEXT NOT NULL
    );
    """,
    """
    CREATE TABLE IF NOT EXISTS pipeline_runs(
      id TEXT PRIMARY KEY, idempotency_key TEXT UNIQUE NOT NULL, state TEXT NOT NULL,
      stage TEXT NOT NULL, progress REAL NOT NULL, request_json TEXT NOT NULL,
      request_hash TEXT NOT NULL, harness TEXT NOT NULL, teacher_model TEXT NOT NULL,
      student_model TEXT NOT NULL, provider_job_id TEXT, error_summary TEXT,
      created_at TEXT NOT NULL, updated_at TEXT NOT NULL, finished_at TEXT
    );
    CREATE TABLE IF NOT EXISTS pipeline_events(
      id INTEGER PRIMARY KEY AUTOINCREMENT, run_id TEXT NOT NULL, sequence INTEGER NOT NULL,
      occurred_at TEXT NOT NULL, state TEXT NOT NULL, stage TEXT NOT NULL,
      progress REAL NOT NULL, message TEXT NOT NULL, details_json TEXT NOT NULL,
      UNIQUE(run_id, sequence), FOREIGN KEY(run_id) REFERENCES pipeline_runs(id)
    );
    CREATE TABLE IF NOT EXISTS cost_comparisons(
      id TEXT PRIMARY KEY, created_at TEXT NOT NULL, comparable INTEGER NOT NULL,
      inputs_json TEXT NOT NULL, result_json TEXT NOT NULL
    );
    """,
    """
    CREATE TABLE IF NOT EXISTS schedule_fires(
      id TEXT PRIMARY KEY, schedule_id TEXT NOT NULL, intended_fire_at TEXT NOT NULL,
      fire_key TEXT UNIQUE NOT NULL, state TEXT NOT NULL, started_at TEXT,
      finished_at TEXT, workflow_run_id TEXT, error_summary TEXT,
      details_json TEXT NOT NULL, FOREIGN KEY(schedule_id) REFERENCES schedules(id) ON DELETE CASCADE
    );
    CREATE TABLE IF NOT EXISTS scheduler_leases(
      name TEXT PRIMARY KEY, owner TEXT NOT NULL, acquired_at TEXT NOT NULL,
      expires_at TEXT NOT NULL
    );
    CREATE INDEX IF NOT EXISTS idx_schedules_due ON schedules(enabled,next_fire_at);
    CREATE INDEX IF NOT EXISTS idx_schedule_fires_schedule ON schedule_fires(schedule_id,intended_fire_at);
    """,
    """
    CREATE TABLE IF NOT EXISTS notification_profiles(
      id TEXT PRIMARY KEY, name TEXT NOT NULL, channel TEXT NOT NULL,
      config_json TEXT NOT NULL, enabled INTEGER NOT NULL, created_at TEXT NOT NULL,
      updated_at TEXT NOT NULL
    );
    CREATE TABLE IF NOT EXISTS notification_subscriptions(
      id TEXT PRIMARY KEY, profile_id TEXT NOT NULL, topic TEXT NOT NULL,
      minimum_severity TEXT NOT NULL, enabled INTEGER NOT NULL, created_at TEXT NOT NULL,
      UNIQUE(profile_id,topic), FOREIGN KEY(profile_id) REFERENCES notification_profiles(id) ON DELETE CASCADE
    );
    CREATE INDEX IF NOT EXISTS idx_notification_subscriptions_topic ON notification_subscriptions(topic,enabled);
    """,
    """
    CREATE TABLE IF NOT EXISTS evaluation_runs(
      id TEXT PRIMARY KEY, definition_id TEXT NOT NULL, definition_version INTEGER NOT NULL,
      model_id TEXT NOT NULL, comparison_model_id TEXT, state TEXT NOT NULL,
      parameters_json TEXT NOT NULL, harness TEXT, config_hash TEXT NOT NULL,
      created_at TEXT NOT NULL, started_at TEXT, finished_at TEXT,
      result_json TEXT NOT NULL, error_summary TEXT
    );
    CREATE TABLE IF NOT EXISTS evaluation_suggestions(
      id TEXT PRIMARY KEY, intent_hash TEXT NOT NULL, harness TEXT,
      suggestion_json TEXT NOT NULL, created_at TEXT NOT NULL, expires_at TEXT NOT NULL,
      accepted_at TEXT
    );
    """,
]


class Database:
    def __init__(self, path: Path):
        self.path = path
        self.path.parent.mkdir(parents=True, exist_ok=True)

    @contextmanager
    def connect(self):
        connection = sqlite3.connect(self.path)
        connection.row_factory = sqlite3.Row
        connection.execute("PRAGMA foreign_keys=ON")
        try:
            yield connection
            connection.commit()
        except Exception:
            connection.rollback()
            raise
        finally:
            connection.close()

    def migrate(self) -> None:
        with self.connect() as connection:
            connection.execute("CREATE TABLE IF NOT EXISTS schema_migrations(version INTEGER PRIMARY KEY, applied_at TEXT NOT NULL)")
            applied = {row[0] for row in connection.execute("SELECT version FROM schema_migrations")}
            for version, script in enumerate(MIGRATIONS, 1):
                if version in applied:
                    continue
                connection.executescript(script)
                connection.execute("INSERT INTO schema_migrations VALUES (?, datetime('now'))", (version,))
