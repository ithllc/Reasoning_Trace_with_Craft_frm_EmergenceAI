#!/usr/bin/env python3
"""Budget-gated, dashboard-grounded voice Q&A service for the local UI."""

from __future__ import annotations

import json
import os
import threading
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

ROOT = Path(__file__).resolve().parents[1]
LEDGER_LOCK = threading.Lock()


def load_dotenv() -> None:
    path = ROOT / ".env"
    if not path.exists():
        return
    for line in path.read_text().splitlines():
        line = line.strip()
        if line and not line.startswith("#") and "=" in line:
            key, value = line.split("=", 1)
            os.environ.setdefault(key.strip(), value.strip().strip('"').strip("'"))


def settings() -> dict:
    load_dotenv()
    return {
        "api_key": os.getenv("NEBIUS_API_KEY", ""),
        "base_url": os.getenv("NEBIUS_BASE_URL", "https://api.tokenfactory.nebius.com/v1/").rstrip("/"),
        "model": os.getenv("VOICE_ASSISTANT_MODEL", ""),
        "max_usd": float(os.getenv("VOICE_ASSISTANT_MAX_BUDGET_USD", "75")),
        "input_per_million": float(os.getenv("VOICE_ASSISTANT_INPUT_USD_PER_MILLION", "0")),
        "output_per_million": float(os.getenv("VOICE_ASSISTANT_OUTPUT_USD_PER_MILLION", "0")),
        "max_output_tokens": int(os.getenv("VOICE_ASSISTANT_MAX_OUTPUT_TOKENS", "500")),
        "dashboard_url": os.getenv("VOICE_ASSISTANT_DASHBOARD_URL", "http://127.0.0.1:8765/api/dashboard"),
        "ledger": Path(os.getenv("VOICE_ASSISTANT_LEDGER", str(ROOT / "runs" / "voice-budget.json"))),
    }


def read_json_url(url: str, request: Request | None = None, timeout: int = 30) -> dict:
    with urlopen(request or url, timeout=timeout) as response:
        return json.loads(response.read())


def read_ledger(path: Path) -> dict:
    if not path.exists():
        return {"spent_usd": 0.0, "requests": 0, "input_tokens": 0, "output_tokens": 0}
    return json.loads(path.read_text())


def write_ledger(path: Path, ledger: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(".tmp")
    temporary.write_text(json.dumps(ledger, indent=2) + "\n")
    temporary.replace(path)


def token_cost(config: dict, input_tokens: int, output_tokens: int) -> float:
    return (
        input_tokens * config["input_per_million"]
        + output_tokens * config["output_per_million"]
    ) / 1_000_000


def public_status(config: dict | None = None) -> dict:
    config = config or settings()
    with LEDGER_LOCK:
        ledger = read_ledger(config["ledger"])
    configured = bool(
        config["api_key"] and config["model"]
        and config["input_per_million"] > 0 and config["output_per_million"] > 0
        and 0 < config["max_usd"] <= 75
    )
    return {
        "configured": configured,
        "model": config["model"] or None,
        "spent_usd": round(float(ledger.get("spent_usd", 0)), 6),
        "budget_usd": config["max_usd"],
        "remaining_usd": round(max(0, config["max_usd"] - float(ledger.get("spent_usd", 0))), 6),
        "requests": int(ledger.get("requests", 0)),
    }


def ask(question: str, config: dict | None = None) -> dict:
    config = config or settings()
    if not question.strip() or len(question) > 2000:
        raise ValueError("Question must contain 1–2,000 characters.")
    status = public_status(config)
    if not status["configured"]:
        raise RuntimeError("Voice inference is disabled: configure model, API key, positive pricing, and a budget no greater than $75.")

    dashboard = read_json_url(config["dashboard_url"], timeout=10)
    dashboard_text = json.dumps(dashboard, separators=(",", ":"), ensure_ascii=True)
    messages = [
        {"role": "system", "content": (
            "You explain the CRAFT Reasoning Lab dashboard. Answer only from the dashboard JSON supplied. "
            "Be concise, define technical terms in plain language, distinguish training loss from benchmark scores, "
            "and say when the dashboard does not contain the answer. Never expose credentials."
        )},
        {"role": "user", "content": f"DASHBOARD JSON:\n{dashboard_text}\n\nQUESTION:\n{question.strip()}"},
    ]
    # Conservative pre-call reservation: approximate all prompt characters at one token each.
    estimated_input = sum(len(item["content"]) for item in messages)
    reserved_cost = token_cost(config, estimated_input, config["max_output_tokens"])
    with LEDGER_LOCK:
        ledger = read_ledger(config["ledger"])
        if float(ledger.get("spent_usd", 0)) + reserved_cost > config["max_usd"]:
            raise RuntimeError("Budget ceiling reached; no inference request was sent.")

        payload = json.dumps({
            "model": config["model"], "messages": messages,
            "max_tokens": config["max_output_tokens"], "temperature": 0.2,
        }).encode()
        request = Request(
            f'{config["base_url"]}/chat/completions', data=payload, method="POST",
            headers={"Authorization": f'Bearer {config["api_key"]}', "Content-Type": "application/json"},
        )
        try:
            result = read_json_url("", request=request, timeout=60)
        except HTTPError as error:
            detail = error.read().decode(errors="replace")[:500]
            raise RuntimeError(f"Nebius inference failed ({error.code}): {detail}") from error
        except URLError as error:
            raise RuntimeError(f"Nebius inference unavailable: {error.reason}") from error

        usage = result.get("usage", {})
        input_tokens = int(usage.get("prompt_tokens", estimated_input))
        output_tokens = int(usage.get("completion_tokens", config["max_output_tokens"]))
        cost = token_cost(config, input_tokens, output_tokens)
        ledger["spent_usd"] = float(ledger.get("spent_usd", 0)) + cost
        ledger["requests"] = int(ledger.get("requests", 0)) + 1
        ledger["input_tokens"] = int(ledger.get("input_tokens", 0)) + input_tokens
        ledger["output_tokens"] = int(ledger.get("output_tokens", 0)) + output_tokens
        write_ledger(config["ledger"], ledger)

    choices = result.get("choices", [])
    if not choices:
        raise RuntimeError("Nebius returned no answer.")
    return {"answer": choices[0]["message"]["content"], "cost_usd": round(cost, 6), "budget": public_status(config)}


class Handler(BaseHTTPRequestHandler):
    def origin_allowed(self) -> bool:
        return self.headers.get("Origin") in {None, "http://127.0.0.1:8765"}

    def send_json(self, value: object, status: int = 200) -> None:
        body = json.dumps(value).encode()
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Access-Control-Allow-Origin", "http://127.0.0.1:8765")
        self.send_header("Access-Control-Allow-Headers", "Content-Type")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_OPTIONS(self) -> None:  # noqa: N802
        if not self.origin_allowed():
            self.send_error(HTTPStatus.FORBIDDEN)
            return
        self.send_response(HTTPStatus.NO_CONTENT)
        self.send_header("Access-Control-Allow-Origin", "http://127.0.0.1:8765")
        self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type")
        self.end_headers()

    def do_GET(self) -> None:  # noqa: N802
        if self.path == "/api/voice/status":
            self.send_json(public_status())
        else:
            self.send_error(HTTPStatus.NOT_FOUND)

    def do_POST(self) -> None:  # noqa: N802
        if self.path != "/api/voice/ask":
            self.send_error(HTTPStatus.NOT_FOUND)
            return
        if not self.origin_allowed():
            self.send_json({"error": "Browser origin is not allowed."}, 403)
            return
        try:
            length = int(self.headers.get("Content-Length", "0"))
            payload = json.loads(self.rfile.read(length) or b"{}")
            self.send_json(ask(str(payload.get("question", ""))))
        except (ValueError, RuntimeError) as error:
            self.send_json({"error": str(error)}, 400)
        except Exception as error:
            self.send_json({"error": f"Voice service error: {error}"}, 500)


def main() -> None:
    server = ThreadingHTTPServer(("127.0.0.1", 8766), Handler)
    print("Dashboard voice assistant: http://127.0.0.1:8766")
    server.serve_forever()


if __name__ == "__main__":
    main()
