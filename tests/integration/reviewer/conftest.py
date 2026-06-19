"""Shared fixtures for reviewer integration tests."""

from __future__ import annotations

from pathlib import Path
from typing import Any
from unittest.mock import MagicMock

import pytest


def _make_tool_use_response(
    action: str, confidence: float = 0.9, target_slug: str | None = None
) -> MagicMock:
    """Build a mock Anthropic response that calls emit_decision."""
    tool_input: dict[str, Any] = {
        "action": action,
        "confidence": confidence,
        "rationale": f"Test rationale for {action}.",
    }
    if target_slug:
        tool_input["target_slug"] = target_slug

    block = MagicMock()
    block.type = "tool_use"
    block.name = "emit_decision"
    block.input = tool_input

    usage = MagicMock()
    usage.input_tokens = 500
    usage.output_tokens = 80
    usage.cache_read_input_tokens = 200
    usage.cache_creation_input_tokens = 0

    response = MagicMock()
    response.content = [block]
    response.usage = usage
    return response


@pytest.fixture
def reviewer_world(tmp_path: Path) -> dict[str, Path]:
    """Isolated queue + threads dirs for reviewer tests."""
    world = {
        "queue": tmp_path / "queue",
        "threads": tmp_path / "threads",
        "catalog": tmp_path / "catalog",
    }
    for p in world.values():
        p.mkdir(parents=True)
    return world


@pytest.fixture
def make_tool_use_response():
    return _make_tool_use_response


def write_queue_item(queue_dir: Path, slug: str, kind: str = "article", **extra) -> Path:
    """Write a minimal queue candidate file."""
    fm_lines = [
        "---",
        f"slug: {slug}",
        f"kind: {kind}",
        f"title: {slug.replace('-', ' ').title()}",
        "source:",
        "  url: https://example.com/test",
        "discovered:",
        "  via: hackernews",
    ]
    for k, v in extra.items():
        fm_lines.append(f"{k}: {v}")
    fm_lines.append("---")
    body = f"Body content for {slug}."
    content = "\n".join(fm_lines) + "\n" + body + "\n"

    # Use a filename that matches real queue files
    path = queue_dir / f"2026-06-19-{slug}-abc12345.md"
    path.write_text(content)
    return path
