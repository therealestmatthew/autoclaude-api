"""Shared data types for the scout subsystem.

Pydantic models for the in-memory representation of:
  - sources we poll (one model per source `type`)
  - candidates we surface
  - per-source state we persist between runs
"""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field

# Mirrors `kind` enum in conventions/kinds.md.
AssetKind = Literal[
    "agent", "skill", "plugin", "mcp", "prompt",
    "repo", "article", "person", "org",
]


class Candidate(BaseModel):
    """A discovered item, awaiting human review in /scout/queue/.

    Flat shape for extractor convenience; the runner converts this into the
    nested catalog frontmatter when writing the queue file.
    """

    name: str                                 # best-guess slug
    kind: AssetKind
    title: str
    source_type: str
    source_url: str
    source_authors: list[str] = Field(default_factory=list)
    source_license: str = ""
    discovered_via: str
    discovered_on: str                        # ISO date (YYYY-MM-DD)
    run_id: str
    raw_title: str | None = None
    raw_url: str | None = None
    score: int | None = None
    excerpt: str | None = None


class AwesomeListEntry(BaseModel):
    name: str
    url: str


class AwesomeListSource(BaseModel):
    name: str
    type: Literal["awesome-list"]
    enabled: bool = True
    poll_interval_minutes: int = 1440
    lists: list[AwesomeListEntry]
    notes: str | None = None


class SourceState(BaseModel):
    """Persisted per-source state. One JSON file per source slug."""

    source: str
    last_run_at: str | None = None
    seen_urls: dict[str, str] = Field(default_factory=dict)   # url -> first_seen_date
    cursor: dict = Field(default_factory=dict)                # source-specific
    stats: dict = Field(default_factory=dict)                 # cumulative counters
