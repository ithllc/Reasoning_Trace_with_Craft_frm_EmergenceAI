#!/usr/bin/env python3
"""Project-scoped CRAFT MCP helper using Codex's OAuth token cache."""

from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path
from typing import Any

import anyio
from mcp import ClientSession
from mcp.client.streamable_http import streamablehttp_client
from mcp.types import ElicitRequestParams, ElicitResult

ROOT = Path(__file__).resolve().parents[1]
CODEX_CREDENTIALS = Path.home() / ".codex" / ".credentials.json"
CRAFT_URL = "https://nebius.emergence.ai/mcp"
PROJECT_ID = "8c5c41d7-19e0-45ba-8bf6-57fc2706bf1b"
GITHUB_CONNECTION = "github-repos-8c5c41d7"


def oauth_token() -> str:
    data = json.loads(CODEX_CREDENTIALS.read_text(encoding="utf-8"))
    for credential in data.values():
        if isinstance(credential, dict) and credential.get("server_name") == "craft":
            token = credential.get("access_token")
            if token:
                return token
    raise RuntimeError("No CRAFT OAuth token found; run `codex mcp login craft`")


def github_response(schema: dict[str, Any]) -> dict[str, Any]:
    """Fill an elicitation schema with the user-authorized GitHub selection."""
    result: dict[str, Any] = {}
    for name, definition in schema.get("properties", {}).items():
        choices = definition.get("enum", [])
        github = next((choice for choice in choices if "github" in str(choice).lower()), None)
        if github is not None:
            result[name] = github
        elif definition.get("type") == "boolean":
            result[name] = True
        elif definition.get("type") == "string":
            result[name] = "GitHub"
    return result


async def elicitation(_context: Any, params: ElicitRequestParams) -> ElicitResult:
    content = github_response(params.requestedSchema)
    print(json.dumps({"elicitation": params.message, "response": content}), file=sys.stderr)
    return ElicitResult(action="accept", content=content)


def content_json(result: Any) -> Any:
    structured = getattr(result, "structuredContent", None)
    if structured is not None:
        return structured
    blocks = []
    for block in getattr(result, "content", []):
        text = getattr(block, "text", None)
        if text is None:
            continue
        try:
            blocks.append(json.loads(text))
        except json.JSONDecodeError:
            blocks.append(text)
    return blocks


async def run(command: str, output: Path | None = None) -> None:
    headers = {
        "Authorization": f"Bearer {oauth_token()}",
        "X-Project-ID": os.environ.get("CRAFT_PROJECT_ID", PROJECT_ID),
    }
    async with streamablehttp_client(CRAFT_URL, headers=headers) as (read, write, _):
        async with ClientSession(read, write, elicitation_callback=elicitation) as session:
            await session.initialize()
            tools = await session.list_tools()
            if command == "tools":
                payload = [{"name": tool.name, "description": tool.description, "inputSchema": tool.inputSchema} for tool in tools.tools]
                print(json.dumps(payload, indent=2))
                return
            names = {tool.name for tool in tools.tools}
            if "list_data_connections" not in names:
                raise RuntimeError("CRAFT does not expose list_data_connections")
            connections_result = await session.call_tool("list_data_connections", {"search": "GITHUB_REPOS"})
            if connections_result.isError:
                raise RuntimeError(json.dumps(content_json(connections_result)))
            connection_data = content_json(connections_result)
            connection = os.environ.get("CRAFT_DEMO_CONNECTION", GITHUB_CONNECTION)
            databases_result = await session.call_tool("list_databases", {"connection": connection, "limit": 200})
            if databases_result.isError:
                raise RuntimeError(json.dumps(content_json(databases_result)))
            payload = {
                "selected_connection": connection,
                "connection_search": connection_data,
                "databases": content_json(databases_result),
            }
            if command == "github-schema":
                database_fqn = f"{connection}.GITHUB_REPOS"
                schema_result = await session.call_tool("get_schema", {
                    "connection": connection, "fqn": database_fqn, "include_children": True,
                })
                if schema_result.isError:
                    raise RuntimeError(json.dumps(content_json(schema_result)))
                database_schema = content_json(schema_result)
                payload["database_schema"] = database_schema
                schemas = database_schema.get("metadata", {}).get("children", [])
                payload["schemas"] = []
                for schema in schemas:
                    schema_fqn = schema["fully_qualified_name"]
                    tables_result = await session.call_tool("get_schema", {
                        "connection": connection, "fqn": schema_fqn, "include_children": True,
                    })
                    if tables_result.isError:
                        raise RuntimeError(json.dumps(content_json(tables_result)))
                    schema_data = content_json(tables_result)
                    table_details = []
                    for table in schema_data.get("metadata", {}).get("children", []):
                        table_result = await session.call_tool("get_schema", {
                            "connection": connection,
                            "fqn": table["fully_qualified_name"],
                            "include_children": True,
                        })
                        if table_result.isError:
                            raise RuntimeError(json.dumps(content_json(table_result)))
                        table_details.append(content_json(table_result))
                    payload["schemas"].append({"schema": schema_data, "tables": table_details})
            rendered = json.dumps(payload, indent=2)
            if output:
                output.parent.mkdir(parents=True, exist_ok=True)
                output.write_text(rendered + "\n", encoding="utf-8")
                print(str(output))
            else:
                print(rendered)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("command", choices=["tools", "github-catalog", "github-schema"])
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    try:
        anyio.run(run, args.command, args.output)
        return 0
    except Exception as error:
        print(f"error: {error}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
