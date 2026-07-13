#!/usr/bin/env python3
"""Fail closed on known secret shapes and private productization identifiers."""

from __future__ import annotations

import argparse
import re
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SKIP_DIRS = {".git", ".venv", "__pycache__", "planning", "runs"}
TEXT_SUFFIXES = {".py", ".md", ".json", ".jsonl", ".toml", ".html", ".example", ""}
PATTERNS = {
    "bearer credential": re.compile(r"(?i)bearer\s+[A-Za-z0-9._-]{12,}"),
    "common API token": re.compile(r"\b(?:sk|ghp|xox[baprs])-[A-Za-z0-9_-]{8,}\b"),
    "populated secret assignment": re.compile(r"(?i)(?:api[_-]?key|access[_-]?token|client[_-]?secret|password)\s*[=:]\s*['\"]?[A-Za-z0-9_/+.-]{12,}"),
    "event project identifier": re.compile(r"8c5c41d7|aiproject-e00g1a833vjes1bvhv"),
    "private event endpoint": re.compile(r"nebius\.emergence\.ai|runtime\.prod\.emergence\.ai"),
}
ALLOW_LINES = {"Bearer secret", "NEBIUS_API_KEY=...", "NEBIUS_API_KEY=<", "replace-with-your-project-id"}


def scan_tree() -> list[str]:
    findings = []
    listed = subprocess.run(["git", "ls-files", "--cached", "--others", "--exclude-standard"], cwd=ROOT,
                            text=True, capture_output=True, check=True).stdout.splitlines()
    for relative_name in sorted(listed):
        path = ROOT / relative_name
        if not path.is_file() or any(part in SKIP_DIRS for part in path.relative_to(ROOT).parts):
            continue
        if path.name == "security_scan.py":
            continue
        if path.suffix.lower() not in TEXT_SUFFIXES and path.name not in {".env.example", ".gitignore"}:
            continue
        try:
            text = path.read_text(encoding="utf-8")
        except UnicodeDecodeError:
            continue
        for number, line in enumerate(text.splitlines(), 1):
            if any(marker in line for marker in ALLOW_LINES):
                continue
            for label, pattern in PATTERNS.items():
                if pattern.search(line):
                    findings.append(f"{path.relative_to(ROOT)}:{number}: {label}")
    return findings


def scan_history() -> list[str]:
    findings = []
    revisions = subprocess.run(["git", "rev-list", "--all"], cwd=ROOT, text=True, capture_output=True, check=True).stdout.splitlines()
    for revision in revisions:
        result = subprocess.run(["git", "grep", "-I", "-l", "-E", "8c5c41d7|aiproject-e00g1a833vjes1bvhv|nebius\\.emergence\\.ai", revision],
                                cwd=ROOT, text=True, capture_output=True)
        if result.returncode == 0:
            findings.append(f"history:{revision[:12]}: restricted identifier found")
    return findings


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--history", action="store_true", help="also scan every Git revision; reports fingerprints only")
    args = parser.parse_args()
    findings = scan_tree() + (scan_history() if args.history else [])
    if findings:
        print("\n".join(findings))
        return 1
    print("security scan passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
