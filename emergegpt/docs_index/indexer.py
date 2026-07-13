"""Allowlisted, hash-addressed local documentation catalog."""

from __future__ import annotations

import hashlib
import json
import re
from pathlib import Path

from ..db import Database

ALLOWED_TEXT = {".md", ".json", ".toml"}
BLOCKED_PARTS = {".git", "planning", "data/private", "node_modules", ".venv"}


def _allowed(root: Path, path: Path) -> bool:
    relative = path.resolve().relative_to(root.resolve()).as_posix()
    return (
        path.suffix.lower() in ALLOWED_TEXT
        and not any(relative == part or relative.startswith(part + "/") for part in BLOCKED_PARTS)
        and not path.name.startswith(".env")
        and not relative.startswith(("data/generated/", "artifacts/", "runs/"))
    )


def build(root: Path, db: Database) -> dict:
    sources = []
    for path in sorted(root.rglob("*")):
        if not path.is_file() or not _allowed(root, path):
            continue
        content = path.read_text(encoding="utf-8", errors="strict")
        if re.search(r"(?i)(bearer\s+[A-Za-z0-9]|api[_-]?key\s*[:=]\s*[^\s\"']+)", content):
            continue
        title = next((line.lstrip("# ").strip() for line in content.splitlines() if line.startswith("#")), path.name)
        item = {"path": path.relative_to(root).as_posix(), "title": title,
                "sha256": hashlib.sha256(content.encode()).hexdigest(), "content": content}
        sources.append(item)
    with db.connect() as connection:
        connection.execute("DELETE FROM documentation_sources")
        connection.executemany(
            "INSERT INTO documentation_sources(path,sha256,title,verified_at,content) VALUES (?,?,?,datetime('now'),?)",
            [(item["path"], item["sha256"], item["title"], item["content"]) for item in sources],
        )
    manifest = [{key: item[key] for key in ("path", "title", "sha256")} for item in sources]
    return {"source_count": len(sources), "build_hash": hashlib.sha256(json.dumps(manifest, sort_keys=True).encode()).hexdigest(),
            "sources": manifest}


def search(db: Database, query: str, limit: int = 8) -> list[dict]:
    terms = [term.lower() for term in re.findall(r"[A-Za-z0-9_-]+", query) if len(term) > 2]
    if not terms:
        return []
    with db.connect() as connection:
        rows = connection.execute("SELECT path,title,sha256,content FROM documentation_sources").fetchall()
    ranked = []
    for row in rows:
        haystack = (row["title"] + "\n" + row["content"]).lower()
        score = sum(haystack.count(term) for term in terms)
        if score:
            excerpt_start = min((haystack.find(term) for term in terms if term in haystack), default=0)
            excerpt = row["content"][max(0, excerpt_start - 120):excerpt_start + 500].strip()
            ranked.append({"path": row["path"], "title": row["title"], "sha256": row["sha256"],
                           "score": score, "excerpt": excerpt})
    return sorted(ranked, key=lambda item: (-item["score"], item["path"]))[: max(1, min(limit, 25))]
