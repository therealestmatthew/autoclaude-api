"""Build the system and user prompts for the reviewer agent.

The system prompt + merge rules + asset schema are cached via Anthropic's
prompt-caching API (cache_control: ephemeral). The per-candidate user message
is the only fresh-token portion, keeping cost-per-review low.
"""

from __future__ import annotations

from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
_MERGE_RULES_PATH = REPO_ROOT / "conventions" / "merge-rules.md"
_SCHEMA_PATH = REPO_ROOT / "catalog" / "_schema" / "asset.schema.md"

# Loaded once at import time; both files are small and rarely change.
_MERGE_RULES: str = _MERGE_RULES_PATH.read_text()
_ASSET_SCHEMA: str = _SCHEMA_PATH.read_text()

_SYSTEM_TEXT = """\
You are the reviewer for the ft-autoclaude catalog. Your job is to triage each \
queue candidate and propose one of three actions: keep, merge, or discard.

Guidelines:
- keep: The item has lasting value for the operator's agentic consulting \
  practice. It should eventually live in /catalog/.
- merge: The item is substantially the same as an existing catalog asset. \
  You MUST name the existing slug as target_slug.
- discard: The item has no lasting value (transient news, low-signal reactions, \
  duplicates without a clear merge target).

You do NOT write catalog files. You do NOT set quality scores. You do NOT \
propose status: adopted — those are operator decisions.

Content drives the decision, not the author's reputation. A notable author \
writing a one-line reaction is a discard; the same author writing a substantive \
analysis is a keep.

When proposing keep, suggest a clean catalog slug (kebab-case, drop "show-hn-" \
prefixes, under 40 chars) in suggested_slug if the current slug is poor.

When you flag url_target (subdir URL ambiguity), always bias toward keeping \
the subdir URL the candidate already has — never auto-pick the parent repo.

Call the emit_decision tool exactly once with your structured decision.\
"""


def build_messages(
    candidate_text: str,
    context_items: list[dict],
    dedup_hints: dict | None = None,
    liveness_hints: dict | None = None,
) -> list[dict]:
    """Return the messages list for the Anthropic API call.

    The system prompt blocks carry cache_control so repeated calls in the same
    batch reuse cached tokens. The user message is always fresh.
    """
    user_parts = [
        {
            "type": "text",
            "text": f"Candidate:\n{candidate_text}",
        }
    ]

    if context_items:
        ctx_lines = ["Nearby catalog assets (top matches):"]
        for i, item in enumerate(context_items, 1):
            tags = ", ".join(item.get("tags", []))
            ctx_lines.append(
                f"  {i}. catalog/{item['slug']}: {item.get('title', '?')}  "
                f"(kind={item.get('kind', '?')}, status={item.get('status', '?')}"
                + (f", tags=[{tags}]" if tags else "")
                + ")"
            )
            if item.get("body_excerpt"):
                ctx_lines.append(f"     {item['body_excerpt'][:100]}")
        user_parts.append({"type": "text", "text": "\n".join(ctx_lines)})

    hint_lines = []
    if dedup_hints:
        mid = dedup_hints.get("mergeset_id") or "none"
        dup = dedup_hints.get("duplicates_via_url") or "none"
        hint_lines.append(
            f"Phase 6 dedup hints:\n  mergeset_id: {mid}\n  duplicates_via_url: {dup}"
        )
    if liveness_hints:
        status = liveness_hints.get("url_status") or "unknown"
        cnt = liveness_hints.get("error_404_count", 0)
        hint_lines.append(f"Phase 7 liveness:\n  source url status: {status}\n  404_count: {cnt}")
    if hint_lines:
        user_parts.append({"type": "text", "text": "\n\n".join(hint_lines)})

    return [{"role": "user", "content": user_parts}]


def build_system_blocks() -> list[dict]:
    """Return the system prompt as a list of content blocks with cache markers."""
    return [
        {
            "type": "text",
            "text": _SYSTEM_TEXT,
            "cache_control": {"type": "ephemeral"},
        },
        {
            "type": "text",
            "text": (
                f"Merge rules (from /conventions/merge-rules.md):"
                f"\n<rules>\n{_MERGE_RULES}\n</rules>"
            ),
            "cache_control": {"type": "ephemeral"},
        },
        {
            "type": "text",
            "text": (
                f"Asset schema (from /catalog/_schema/asset.schema.md):"
                f"\n<schema>\n{_ASSET_SCHEMA}\n</schema>"
            ),
            "cache_control": {"type": "ephemeral"},
        },
    ]
