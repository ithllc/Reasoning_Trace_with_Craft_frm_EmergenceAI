from __future__ import annotations

import argparse
import json
from pathlib import Path


SYSTEM_PROMPT = (
    "You are a concise Craft data analyst. For natural-language analytics questions, "
    "call generate_sql before execute_query, pass the generated SQL unchanged, retrieve "
    "the result page, and ground the final answer only in returned rows. Provide a short "
    "decision summary, never hidden chain-of-thought."
)


def tool_call(call_id: str, name: str, arguments: dict) -> dict:
    return {
        "id": call_id,
        "type": "function",
        "function": {"name": name, "arguments": json.dumps(arguments, separators=(",", ":"))},
    }


def convert(row: dict) -> dict:
    run_id = row["id"]
    schema = {"schema_name": row["schema_name"], "schema_fqn": row["schema_fqn"]}
    generate_id = f"{run_id}-generate"
    execute_id = f"{run_id}-execute"
    page_id = f"{run_id}-page"
    sql = row["sql"]
    artifact = row["artifact_fqn"]
    messages = [
        {"role": "system", "content": SYSTEM_PROMPT},
        {"role": "user", "content": row["question"]},
        {
            "role": "assistant",
            "content": "Decision summary: generate schema-grounded SQL before querying Craft.",
            "tool_calls": [tool_call(generate_id, "generate_sql", {
                "connection": row["connection"], "question": row["question"], "schema": schema,
            })],
        },
        {"role": "tool", "tool_call_id": generate_id, "name": "generate_sql", "content": json.dumps({
            "sql": sql, "explanation": row["sql_explanation"], "assumptions": row["assumptions"],
        }, separators=(",", ":"))},
        {
            "role": "assistant",
            "content": "Decision summary: execute the generated read-only SQL unchanged.",
            "tool_calls": [tool_call(execute_id, "execute_query", {
                "connection": row["connection"], "sql": sql, "max_rows": 20,
            })],
        },
        {"role": "tool", "tool_call_id": execute_id, "name": "execute_query", "content": json.dumps({
            "artifact_fqn": artifact, "row_count": len(row["rows"]), "truncated": False, "sql": sql,
        }, separators=(",", ":"))},
        {
            "role": "assistant",
            "content": "Decision summary: retrieve the result rows before answering.",
            "tool_calls": [tool_call(page_id, "get_result_page", {
                "artifact_fqn": artifact, "offset": 0, "limit": 20,
            })],
        },
        {"role": "tool", "tool_call_id": page_id, "name": "get_result_page", "content": json.dumps({
            "columns": row["columns"], "rows": row["rows"], "total_rows": len(row["rows"]),
            "truncated": False,
        }, separators=(",", ":"))},
        {"role": "assistant", "content": row["final_answer"]},
    ]
    return {"id": run_id, "model": "Qwen/Qwen3.5-9B", "status": "completed", "messages": messages}


def main() -> None:
    parser = argparse.ArgumentParser(description="Convert reviewed Craft run receipts to chat trajectories")
    parser.add_argument("source", type=Path)
    parser.add_argument("output", type=Path)
    args = parser.parse_args()
    rows = [json.loads(line) for line in args.source.read_text(encoding="utf-8").splitlines() if line.strip()]
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text("".join(json.dumps(convert(row)) + "\n" for row in rows), encoding="utf-8")
    print(f"Converted: {len(rows)} reviewed Craft runs -> {args.output}")


if __name__ == "__main__":
    main()
