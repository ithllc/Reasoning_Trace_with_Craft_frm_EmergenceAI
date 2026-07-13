"""Shared EmergeGPT MCP server initialization."""

from __future__ import annotations

import os

from emergegpt.db import Database
from emergegpt.docs_index.indexer import build, search
from emergegpt.settings import ROOT, Settings


def runtime():
    settings = Settings.load()
    database = Database(settings.database_path)
    database.migrate()
    build(ROOT, database)
    return settings, database


def docs_search(database: Database, query: str, domain: str) -> dict:
    domain_terms = f"{domain} {query}"
    return {"data": search(database, domain_terms), "source_kind": "approved_repository_and_public_documentation_index",
            "source_refs": [], "policy": {"live_mutation": False}}
