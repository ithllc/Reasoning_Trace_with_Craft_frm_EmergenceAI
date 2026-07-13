"""CLI argument construction and normalization for supported harnesses."""

from __future__ import annotations

import json

from .base import HarnessRequest, SubprocessHarness


class CodexHarness(SubprocessHarness):
    name, binary = "codex", "codex"
    def command(self, r): return [self.binary, "exec", "--json", *( ["--model", r.model] if r.model else []), r.prompt]
    def normalize(self, output):
        events = [json.loads(line) for line in output.splitlines() if line.strip()]
        return {"events": events[-50:], "event_count": len(events)}


class ClaudeCodeHarness(SubprocessHarness):
    name, binary = "claude_code", "claude"
    def command(self, r): return [self.binary, "-p", r.prompt, "--output-format", "json", "--max-turns", "3"]


class OpenCodeHarness(SubprocessHarness):
    name, binary = "opencode", "opencode"
    def command(self, r): return [self.binary, "run", r.prompt, "--format", "json"]


class OpenClawHarness(SubprocessHarness):
    name, binary = "openclaw", "openclaw"
    def command(self, r): return [self.binary, "agent", "--agent", "emergegpt", "--message", r.prompt, "--timeout", str(r.timeout_seconds), "--json"]
    def normalize(self, output):
        result = json.loads(output)
        meta = result.get("meta", {})
        if meta.get("fallbackFrom") or result.get("deliveryStatus", {}).get("attempted"):
            raise RuntimeError("unexpected OpenClaw fallback or delivery")
        return result


class GeminiCliHarness(SubprocessHarness):
    name, binary = "gemini_cli", "gemini"
    def command(self, r): return [self.binary, "--prompt", r.prompt, "--output-format", "json", "--sandbox", *( ["--model", r.model] if r.model else [])]


class NemoClawHarness(SubprocessHarness):
    name, binary = "nemoclaw", "nemoclaw"
    def __init__(self, sandbox: str = "emergegpt"):
        self.sandbox = sandbox
    def command(self, r): return [self.binary, self.sandbox, "agent", "--agent", "emergegpt", "--json", "-m", r.prompt]


class DirectNebiusHarness:
    name = "direct_nebius"
    def __init__(self, provider): self.provider = provider
    def capabilities(self): return {"name": self.name, "available": bool(self.provider.settings.nebius_api_key), "structured_output": True}
    def run(self, request: HarnessRequest):
        payload = {"model": request.model, "messages": [{"role": "user", "content": request.prompt}], "temperature": 0.2}
        return self.provider.request("POST", "chat/completions", payload)


ALL_HARNESSES = {item.name: item for item in (CodexHarness, ClaudeCodeHarness, OpenCodeHarness, OpenClawHarness, GeminiCliHarness, NemoClawHarness)}
