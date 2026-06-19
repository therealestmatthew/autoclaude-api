"""Pydantic models for the reviewer agent's structured output."""

from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, Field, model_validator


class Decision(BaseModel):
    action: Literal["keep", "merge", "discard"]
    # F2: parent-with-children scope batches a parent + all its queue children.
    scope: Literal["self", "parent-with-children"] = "self"
    # required when action == "merge"
    target_slug: str | None = None
    # F4: suggested catalog slug on keep (strip show-hn- prefixes, shorten, etc.)
    suggested_slug: str | None = None
    # 0..1 calibrated confidence; < 0.6 triggers Opus escalation
    confidence: float = Field(ge=0.0, le=1.0)
    # 2–4 sentence reasoning grounded in the candidate and catalog context
    rationale: str
    # additive tag suggestions only; never proposes removals
    suggested_edits: dict[str, Any] | None = None
    # F6, F7: url_target (subdir/parent/unsure), author_mismatch, etc.
    flags: dict[str, Any] | None = None

    @model_validator(mode="after")
    def _merge_requires_target(self) -> Decision:
        if self.action == "merge" and not self.target_slug:
            raise ValueError("merge requires target_slug")
        return self


# JSON schema for the emit_decision tool — passed to the Anthropic API.
EMIT_DECISION_TOOL: dict[str, Any] = {
    "name": "emit_decision",
    "description": (
        "Emit your structured triage decision for the candidate. "
        "Call this tool exactly once with your decision."
    ),
    "input_schema": {
        "type": "object",
        "properties": {
            "action": {
                "type": "string",
                "enum": ["keep", "merge", "discard"],
                "description": "Triage action for this candidate.",
            },
            "scope": {
                "type": "string",
                "enum": ["self", "parent-with-children"],
                "description": (
                    "Use 'parent-with-children' when the candidate is a parent "
                    "with queue children whose decision cascades from the parent's."
                ),
            },
            "target_slug": {
                "type": ["string", "null"],
                "description": "Existing catalog slug to merge into (required for merge).",
            },
            "suggested_slug": {
                "type": ["string", "null"],
                "description": (
                    "Proposed catalog slug for 'keep' (kebab-case, no show-hn- prefix, "
                    "under 40 chars). Leave null to accept the current slug."
                ),
            },
            "confidence": {
                "type": "number",
                "minimum": 0.0,
                "maximum": 1.0,
                "description": "Calibrated confidence 0..1.",
            },
            "rationale": {
                "type": "string",
                "description": (
                    "2–4 sentence reasoning grounded in the candidate and catalog context."
                ),
            },
            "suggested_edits": {
                "type": ["object", "null"],
                "description": (
                    "Optional additive edits: {'tags': ['new-tag', ...]}. "
                    "Never propose tag removals."
                ),
            },
            "flags": {
                "type": ["object", "null"],
                "description": (
                    "Optional flags: "
                    "url_target ('subdir'|'parent'|'unsure'), "
                    "author_mismatch (bool), notes (str)."
                ),
            },
        },
        "required": ["action", "confidence", "rationale"],
    },
}
