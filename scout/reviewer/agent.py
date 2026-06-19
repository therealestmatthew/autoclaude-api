"""Single-candidate reviewer: calls the Anthropic API and returns a Decision.

Uses the tool-call pattern (emit_decision) for structured output. Retries once
on network failure or malformed tool call. Raises ReviewerError on second failure.
"""

from __future__ import annotations

from typing import Any

from .prompt import build_messages, build_system_blocks
from .schema import EMIT_DECISION_TOOL, Decision

_DEFAULT_MODEL = "claude-sonnet-4-6"
_ESCALATION_MODEL = "claude-opus-4-7"
_ESCALATION_THRESHOLD = 0.6


class ReviewerError(Exception):
    """Raised when the model returns an unusable response after retries."""


def _call_api(
    client: Any,
    model: str,
    system_blocks: list[dict],
    messages: list[dict],
) -> tuple[Decision, dict]:
    """Make one API call and parse the tool-call response.

    Returns (Decision, usage_dict).
    Raises ReviewerError on malformed response.
    """
    response = client.messages.create(
        model=model,
        max_tokens=800,
        temperature=0,
        system=system_blocks,
        tools=[EMIT_DECISION_TOOL],
        tool_choice={"type": "tool", "name": "emit_decision"},
        messages=messages,
    )

    tool_input: dict | None = None
    for block in response.content:
        if getattr(block, "type", None) == "tool_use" and block.name == "emit_decision":
            tool_input = block.input
            break

    if tool_input is None:
        raw = str(response.content)
        raise ReviewerError(f"model did not call emit_decision: {raw[:200]}")

    try:
        decision = Decision.model_validate(tool_input)
    except Exception as exc:
        raise ReviewerError(f"invalid Decision from model: {exc}") from exc

    usage = {
        "input_tokens": getattr(response.usage, "input_tokens", 0),
        "output_tokens": getattr(response.usage, "output_tokens", 0),
        "cache_read_tokens": getattr(response.usage, "cache_read_input_tokens", 0),
        "cache_write_tokens": getattr(response.usage, "cache_creation_input_tokens", 0),
    }
    return decision, usage


def review_candidate(
    client: Any,
    candidate_text: str,
    context_items: list[dict],
    dedup_hints: dict | None = None,
    liveness_hints: dict | None = None,
    model: str = _DEFAULT_MODEL,
    force_model: str | None = None,
) -> tuple[Decision, dict, str]:
    """Review one candidate. Returns (Decision, usage_dict, model_used).

    - Tries `model` (default Sonnet).
    - If confidence < threshold, escalates to Opus (unless force_model is set).
    - Retries once on ReviewerError.
    """
    system_blocks = build_system_blocks()
    messages = build_messages(candidate_text, context_items, dedup_hints, liveness_hints)

    effective_model = force_model or model

    # Attempt 1
    try:
        decision, usage = _call_api(client, effective_model, system_blocks, messages)
    except ReviewerError:
        # Single retry on first failure
        decision, usage = _call_api(client, effective_model, system_blocks, messages)

    model_used = effective_model

    # Escalate to Opus if low confidence and no force_model override
    if (
        not force_model
        and decision.confidence < _ESCALATION_THRESHOLD
        and effective_model != _ESCALATION_MODEL
    ):
        escalation_model = _ESCALATION_MODEL
        try:
            e_decision, e_usage = _call_api(client, escalation_model, system_blocks, messages)
            decision = e_decision
            usage = {
                "input_tokens": usage["input_tokens"] + e_usage["input_tokens"],
                "output_tokens": usage["output_tokens"] + e_usage["output_tokens"],
                "cache_read_tokens": usage["cache_read_tokens"] + e_usage["cache_read_tokens"],
                "cache_write_tokens": usage["cache_write_tokens"] + e_usage["cache_write_tokens"],
                "escalated_from": effective_model,
            }
            model_used = escalation_model
        except ReviewerError:
            # Escalation failed — ship the low-confidence Sonnet decision
            usage["escalation_failed"] = True

    return decision, usage, model_used


def make_candidate_text(
    slug: str,
    frontmatter: dict,
    body: str,
    child_slugs: list[str] | None = None,
) -> str:
    """Render a candidate for inclusion in the user message."""
    source = frontmatter.get("source") or {}
    source_url = source.get("url", "") if isinstance(source, dict) else ""
    discovered = frontmatter.get("discovered") or {}
    via = discovered.get("via", "") if isinstance(discovered, dict) else ""

    lines = [
        f"slug: {slug}",
        f"kind: {frontmatter.get('kind', '?')}",
        f"title: {frontmatter.get('title', '?')}",
        f"source_url: {source_url}",
        f"discovered_via: {via}",
    ]
    if frontmatter.get("tags"):
        lines.append(f"tags: {', '.join(frontmatter['tags'])}")

    source_meta = {}
    if isinstance(source, dict):
        for k in ("hn_score", "reddit_score", "stars", "forks"):
            if source.get(k):
                source_meta[k] = source[k]
    if source_meta:
        lines.append("source_meta: " + ", ".join(f"{k}={v}" for k, v in source_meta.items()))

    if body:
        lines.append(f"body_excerpt: {body[:300].strip()}")

    if child_slugs:
        lines.append(f"children_in_queue ({len(child_slugs)}): " + ", ".join(child_slugs[:5]))
        if len(child_slugs) > 5:
            lines[-1] += f" … (+{len(child_slugs)-5} more)"

    return "\n".join(lines)
