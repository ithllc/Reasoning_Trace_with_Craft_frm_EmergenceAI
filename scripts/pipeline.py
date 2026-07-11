#!/usr/bin/env python3
"""Safe orchestration for CRAFT trace distillation and Nebius fine-tuning."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import random
import subprocess
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_CONFIG = ROOT / "config" / "pipeline.json"


def load_dotenv(path: Path = ROOT / ".env") -> None:
    """Load simple KEY=VALUE entries without overriding the process environment."""
    if not path.exists():
        return
    for raw_line in path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        key = key.strip()
        value = value.strip().strip('"').strip("'")
        if key and key not in os.environ:
            os.environ[key] = value


def load_json(path: Path) -> Any:
    with path.open(encoding="utf-8") as handle:
        return json.load(handle)


def dump_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as handle:
        json.dump(value, handle, indent=2, sort_keys=True)
        handle.write("\n")


def read_jsonl(path: Path) -> list[dict[str, Any]]:
    rows = []
    with path.open(encoding="utf-8") as handle:
        for number, line in enumerate(handle, 1):
            if not line.strip():
                continue
            try:
                value = json.loads(line)
            except json.JSONDecodeError as error:
                raise ValueError(f"{path}:{number}: {error}") from error
            if not isinstance(value, dict):
                raise ValueError(f"{path}:{number}: each line must be a JSON object")
            rows.append(value)
    return rows


def write_jsonl(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as handle:
        for row in rows:
            handle.write(json.dumps(row, separators=(",", ":"), ensure_ascii=False) + "\n")


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def compact_catalog(snapshot: dict[str, Any]) -> dict[str, Any]:
    """Keep grounding fields while removing repetitive CRAFT transport metadata."""
    compact: dict[str, Any] = {
        "connection": snapshot["selected_connection"],
        "database": "GITHUB_REPOS",
        "schemas": [],
    }
    for schema_entry in snapshot.get("schemas", []):
        schema_metadata = schema_entry["schema"]["metadata"]
        compact_schema = {
            "name": schema_metadata["name"],
            "fully_qualified_name": schema_metadata["fully_qualified_name"],
            "description": schema_metadata.get("description"),
            "tables": [],
        }
        for table_entry in schema_entry.get("tables", []):
            table = table_entry["metadata"]
            compact_schema["tables"].append({
                "name": table["name"],
                "fully_qualified_name": table["fully_qualified_name"],
                "description": table.get("description"),
                "summary": table.get("summary_text"),
                "classifications": {
                    "pii": table.get("is_pii_tagged"),
                    "sensitive": table.get("is_sensitivity_tagged"),
                    "data_quality": table.get("is_dq_tagged"),
                    "tags": table.get("tags", []),
                },
                "columns": [{
                    "name": column["name"],
                    "fully_qualified_name": column["fully_qualified_name"],
                    "data_type": column.get("data_type"),
                    "nullable": column.get("nullable"),
                    "description": column.get("description"),
                    "business_definition": column.get("business_definition"),
                    "business_rules": column.get("business_rules"),
                    "pii": column.get("is_pii_tagged"),
                    "sensitive": column.get("is_sensitivity_tagged"),
                    "tags": column.get("tags", []),
                } for column in table.get("children", [])],
            })
        compact["schemas"].append(compact_schema)
    return compact


def api_request(method: str, path: str, *, body: bytes | None = None, content_type: str | None = None) -> Any:
    token = os.environ.get("NEBIUS_API_KEY")
    if not token:
        raise RuntimeError("NEBIUS_API_KEY is required")
    base_url = os.environ.get("NEBIUS_BASE_URL", "https://api.tokenfactory.nebius.com/v1/")
    url = base_url.rstrip("/") + "/" + path.lstrip("/")
    project_id = os.environ.get("NEBIUS_PROJECT_ID")
    if project_id:
        separator = "&" if "?" in url else "?"
        url += separator + urllib.parse.urlencode({"ai_project_id": project_id})
    headers = {"Authorization": f"Bearer {token}", "Accept": "application/json"}
    if content_type:
        headers["Content-Type"] = content_type
    request = urllib.request.Request(url, data=body, headers=headers, method=method)
    try:
        with urllib.request.urlopen(request, timeout=60) as response:
            payload = response.read()
    except urllib.error.HTTPError as error:
        detail = error.read().decode("utf-8", errors="replace")
        raise RuntimeError(f"Nebius API {error.code}: {detail}") from error
    return json.loads(payload) if payload else None


def command_inventory(_: argparse.Namespace) -> int:
    print("CRAFT: documentation MCP; Assets/data connections; agent cards validation/registry; workflows/pipelines; OpenFGA permission checks; Secrets API; Langfuse/OTel traces")
    print("Nebius: models; files; fine_tuning.jobs; job events; checkpoints; Responses/function/MCP tools; deployment APIs")
    return 0


def command_preflight(args: argparse.Namespace) -> int:
    config = load_json(args.config)
    target = config["student"]["model"]
    result = api_request("GET", "models?verbose=true")
    live_ids = {item.get("id") for item in result.get("data", [])}
    family = target.split("/", 1)[-1].split("-", 1)[0].lower()
    related_ids = sorted(model_id for model_id in live_ids if isinstance(model_id, str) and family in model_id.lower())
    report = {
        "checked_at": datetime.now(timezone.utc).isoformat(),
        "target_model": target,
        "present_in_live_model_catalog": target in live_ids,
        "related_live_model_ids": related_ids,
        "documented_fine_tuning_support": config["nebius"]["target_fine_tuning_supported_as_of_2026_07_11"],
        "safe_to_submit": target in live_ids and config["nebius"]["target_fine_tuning_supported_as_of_2026_07_11"],
    }
    print(json.dumps(report, indent=2))
    return 0 if report["safe_to_submit"] else 2


def command_nebius_capabilities(_: argparse.Namespace) -> int:
    models = api_request("GET", "models?verbose=true").get("data", [])
    model_ids = sorted(item["id"] for item in models if isinstance(item.get("id"), str))
    fine_tuning_accessible = False
    fine_tuning_error = None
    job_count_returned = 0
    try:
        jobs = api_request("GET", "fine_tuning/jobs?limit=1")
        fine_tuning_accessible = True
        job_count_returned = len(jobs.get("data", []))
    except RuntimeError as error:
        fine_tuning_error = str(error)
    print(json.dumps({
        "model_count": len(model_ids),
        "models": model_ids,
        "fine_tuning_jobs_api_accessible": fine_tuning_accessible,
        "fine_tuning_jobs_returned": job_count_returned,
        "fine_tuning_error": fine_tuning_error,
    }, indent=2))
    return 0 if fine_tuning_accessible else 2


def command_student_smoke(args: argparse.Namespace) -> int:
    config = load_json(args.config)
    request = {
        "model": config["student"]["model"],
        "messages": [
            {"role": "system", "content": "You are a concise CRAFT GitHub catalog analyst. Give an auditable decision summary, cite supplied catalog fields, and never invent tool results or hidden chain-of-thought."},
            {"role": "user", "content": "A GITHUB_REPOS.SAMPLE_REPOS asset has repo_name and watch_count fields, but no recorded freshness or quality validation. May it be used directly in a customer-facing answer?"},
        ],
        "temperature": 0.2,
        "max_tokens": 256,
    }
    result = api_request("POST", "chat/completions", body=json.dumps(request).encode(), content_type="application/json")
    print(json.dumps({
        "model": result.get("model", config["student"]["model"]),
        "answer": result["choices"][0]["message"]["content"],
        "usage": result.get("usage"),
    }, indent=2))
    return 0


def command_generate(args: argparse.Namespace) -> int:
    config = load_json(args.config)
    seeds = read_jsonl(args.seeds)
    catalog = compact_catalog(load_json(args.catalog))
    output = args.output
    prompt = f"""You are Sol, the Codex teacher for an auditable model-distillation dataset.
Use the supplied read-only CRAFT GitHub catalog snapshot as project-scoped data evidence. Use emergence-craft for public workflow and agent-registry documentation when needed. Do not call live CRAFT tools in this headless run.
Create one high-quality example for every seed below. Return only JSON matching the supplied output schema.
Use concise decision summaries, evidence references, and tool-call summaries. Do not expose or request hidden chain-of-thought.
Never include credentials, private tenant data, or invented APIs. Label uncertainty with validation=needs_review.
Teacher label: {config['teacher']['requested_label']}
Seeds: {json.dumps(seeds, ensure_ascii=False)}
CRAFT GitHub catalog snapshot: {json.dumps(catalog, ensure_ascii=False)}
"""
    raw = output.with_suffix(".teacher.json")
    cmd = [
        "codex", "exec", "--ephemeral", "--sandbox", "read-only",
        "--output-schema", str(ROOT / "schemas" / "teacher-batch.schema.json"),
        "--output-last-message", str(raw), "-",
    ]
    model = os.environ.get(config["teacher"]["model_env"])
    if model:
        cmd[2:2] = ["--model", model]
    subprocess.run(cmd, cwd=ROOT, input=prompt, text=True, check=True)
    batch = load_json(raw)
    rows = []
    for example in batch["examples"]:
        rows.append({"messages": example["messages"], "metadata": {
            "id": example["id"], "domain": example["domain"], "teacher": batch["teacher"],
            "trace": example["trace"],
        }})
    write_jsonl(output, rows)
    print(f"Wrote {len(rows)} examples to {output}")
    return 0


def validate_training_rows(rows: list[dict[str, Any]]) -> list[str]:
    errors = []
    for index, row in enumerate(rows, 1):
        messages = row.get("messages")
        if not isinstance(messages, list) or len(messages) < 2:
            errors.append(f"row {index}: messages must contain at least two entries")
            continue
        for message in messages:
            if message.get("role") not in {"system", "user", "assistant", "tool"} or not isinstance(message.get("content"), str):
                errors.append(f"row {index}: invalid message")
        serialized = json.dumps(row, ensure_ascii=False).lower()
        for marker in ("bearer ", "api_key=", "password="):
            if marker in serialized:
                errors.append(f"row {index}: possible secret marker {marker!r}")
    return errors


def command_prepare(args: argparse.Namespace) -> int:
    config = load_json(args.config)
    rows = read_jsonl(args.input)
    errors = validate_training_rows(rows)
    if errors:
        raise ValueError("\n".join(errors))
    random.Random(config["nebius"]["training"]["seed"]).shuffle(rows)
    fraction = config["nebius"]["training"]["validation_fraction"]
    validation_count = max(1, round(len(rows) * fraction)) if len(rows) > 1 else 0
    validation = rows[:validation_count]
    training = rows[validation_count:]
    write_jsonl(args.output_dir / "train.jsonl", training)
    write_jsonl(args.output_dir / "validation.jsonl", validation)
    manifest = {
        "created_at": datetime.now(timezone.utc).isoformat(),
        "source": str(args.input), "source_sha256": sha256(args.input),
        "train_examples": len(training), "validation_examples": len(validation),
        "student_model": config["student"]["model"], "seed": config["nebius"]["training"]["seed"],
    }
    dump_json(args.output_dir / "manifest.json", manifest)
    print(json.dumps(manifest, indent=2))
    return 0


def upload_file(path: Path) -> str:
    boundary = f"----craft-{uuid.uuid4().hex}"
    parts = []
    for name, value in (("purpose", b"fine-tune"),):
        parts.extend([f"--{boundary}\r\nContent-Disposition: form-data; name=\"{name}\"\r\n\r\n".encode(), value, b"\r\n"])
    parts.extend([
        f"--{boundary}\r\nContent-Disposition: form-data; name=\"file\"; filename=\"{path.name}\"\r\nContent-Type: application/jsonl\r\n\r\n".encode(),
        path.read_bytes(), b"\r\n", f"--{boundary}--\r\n".encode(),
    ])
    result = api_request("POST", "files", body=b"".join(parts), content_type=f"multipart/form-data; boundary={boundary}")
    return result["id"]


def command_submit(args: argparse.Namespace) -> int:
    config = load_json(args.config)
    if not config["nebius"]["target_fine_tuning_supported_as_of_2026_07_11"]:
        raise RuntimeError(f"Blocked: Nebius does not currently document fine-tuning support for {config['student']['model']}. Re-verify official support before changing the gate.")
    train_id = upload_file(args.dataset_dir / "train.jsonl")
    validation_path = args.dataset_dir / "validation.jsonl"
    validation_id = upload_file(validation_path) if validation_path.stat().st_size else None
    request = {
        "model": config["student"]["model"],
        "suffix": config["nebius"]["training"]["suffix"],
        "training_file": train_id,
        "hyperparameters": config["nebius"]["training"]["hyperparameters"],
        "seed": config["nebius"]["training"]["seed"],
    }
    if validation_id:
        request["validation_file"] = validation_id
    result = api_request("POST", "fine_tuning/jobs", body=json.dumps(request).encode(), content_type="application/json")
    run_dir = ROOT / "runs" / result["id"]
    dump_json(run_dir / "submission.json", {"request": request, "response": result})
    print(result["id"])
    return 0


def command_monitor(args: argparse.Namespace) -> int:
    started = time.monotonic()
    while True:
        job = api_request("GET", f"fine_tuning/jobs/{args.job_id}")
        print(json.dumps({"status": job.get("status"), "trained_steps": job.get("trained_steps"), "total_steps": job.get("total_steps")}), flush=True)
        if job.get("status") in {"succeeded", "failed", "cancelled"}:
            dump_json(ROOT / "runs" / args.job_id / "final.json", job)
            return 0 if job.get("status") == "succeeded" else 2
        if time.monotonic() - started >= args.max_seconds:
            cancelled = api_request("POST", f"fine_tuning/jobs/{args.job_id}/cancel")
            dump_json(ROOT / "runs" / args.job_id / "cancelled-at-time-limit.json", cancelled)
            print(json.dumps({"status": cancelled.get("status"), "reason": "15-minute wall-clock limit"}), flush=True)
            return 2
        time.sleep(args.interval)


def command_list_jobs(_: argparse.Namespace) -> int:
    jobs = api_request("GET", "fine_tuning/jobs?limit=20")
    print(json.dumps([{
        "id": job.get("id"), "model": job.get("model"), "status": job.get("status"),
        "created_at": job.get("created_at"), "trained_steps": job.get("trained_steps"),
        "total_steps": job.get("total_steps"), "lora": job.get("hyperparameters", {}).get("lora"),
    } for job in jobs.get("data", [])], indent=2))
    return 0


def command_eval(args: argparse.Namespace) -> int:
    config = load_json(args.config)["evaluations"]
    gen = config["generation"]
    command = [
        "lm_eval", "--model", "hf", "--model_args", f"pretrained={args.model}",
        "--tasks", ",".join(config["tasks"]), "--limit", str(config["limit"]),
        "--apply_chat_template", "--gen_kwargs", f"temperature={gen['temperature']},top_p={gen['top_p']},top_k={gen['top_k']},do_sample=True",
        "--output_path", str(args.output), "--log_samples",
    ]
    print(" ".join(command))
    if args.run:
        subprocess.run(command, cwd=ROOT, check=True)
    return 0


def parser() -> argparse.ArgumentParser:
    result = argparse.ArgumentParser(description=__doc__)
    result.add_argument("--config", type=Path, default=DEFAULT_CONFIG)
    commands = result.add_subparsers(dest="command", required=True)
    commands.add_parser("inventory").set_defaults(func=command_inventory)
    commands.add_parser("preflight-nebius").set_defaults(func=command_preflight)
    commands.add_parser("nebius-capabilities").set_defaults(func=command_nebius_capabilities)
    commands.add_parser("student-smoke").set_defaults(func=command_student_smoke)
    generate = commands.add_parser("generate")
    generate.add_argument("--seeds", type=Path, default=ROOT / "data" / "seeds" / "example-prompts.jsonl")
    generate.add_argument("--output", type=Path, default=ROOT / "data" / "generated" / "teacher.jsonl")
    generate.add_argument("--catalog", type=Path, default=ROOT / "data" / "generated" / "github-catalog-snapshot.json")
    generate.set_defaults(func=command_generate)
    prepare = commands.add_parser("prepare")
    prepare.add_argument("--input", type=Path, required=True)
    prepare.add_argument("--output-dir", type=Path, default=ROOT / "artifacts" / "dataset")
    prepare.set_defaults(func=command_prepare)
    submit = commands.add_parser("submit")
    submit.add_argument("--dataset-dir", type=Path, default=ROOT / "artifacts" / "dataset")
    submit.set_defaults(func=command_submit)
    monitor = commands.add_parser("monitor")
    monitor.add_argument("job_id")
    monitor.add_argument("--interval", type=int, default=15)
    monitor.add_argument("--max-seconds", type=int, default=900)
    monitor.set_defaults(func=command_monitor)
    commands.add_parser("list-jobs").set_defaults(func=command_list_jobs)
    evaluate = commands.add_parser("eval")
    evaluate.add_argument("--model", required=True)
    evaluate.add_argument("--output", type=Path, default=ROOT / "artifacts" / "evals")
    evaluate.add_argument("--run", action="store_true")
    evaluate.set_defaults(func=command_eval)
    return result


def main() -> int:
    load_dotenv()
    args = parser().parse_args()
    try:
        return args.func(args)
    except (OSError, ValueError, RuntimeError, subprocess.CalledProcessError) as error:
        print(f"error: {error}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
