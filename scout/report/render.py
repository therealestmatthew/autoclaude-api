"""Totals → markdown.

Pure function. No timestamps, no random ordering — the same Totals must
produce byte-identical markdown so `scout report --write` is idempotent.
"""

from __future__ import annotations

from .aggregate import Totals


def render(t: Totals) -> str:
    """Render a Totals object as a markdown rollup."""
    lines: list[str] = []
    heading_period = (
        f"{t.period_start.isoformat()} → {t.period_end.isoformat()}"
        if t.period_start != t.period_end
        else t.period_start.isoformat()
    )
    lines.append(f"# Scout health report — {heading_period}")
    lines.append("")

    lines.append("## Headline")
    lines.append("")
    if t.runs == 0:
        lines.append("_No thread-log records in this window._")
        lines.append("")
        return "\n".join(lines) + "\n"

    lines.append(
        f"- Runs: {t.runs} ({t.runs_ok} ok, {t.runs_partial} partial)"
    )
    lines.append(
        f"- Candidates queued: {t.candidates_queued} "
        f"(incl. {t.candidates_via_repo_extraction} via repo extraction)"
    )
    lines.append(
        f"- Identity / URL collapses by dedup: "
        f"{t.dedup_identity + t.dedup_url}"
    )
    lines.append(
        f"- Merge proposals surfaced: {t.merge_proposals_active} active, "
        f"{t.merge_proposals_carried} carried (rejected)"
    )
    lines.append(f"- Catalog auto-archived: {t.auto_archived}")
    lines.append("")

    # By agent (sorted by agent name for determinism).
    lines.append("## By agent")
    lines.append("")
    lines.append("| Agent | Runs | OK | Partial | Errors | Notable |")
    lines.append("| --- | ---: | ---: | ---: | ---: | --- |")
    for agent in sorted(t.by_agent.keys()):
        a = t.by_agent[agent]
        notable = "; ".join(a.notable[:3]) if a.notable else "—"
        lines.append(
            f"| {agent} | {a.runs} | {a.ok} | {a.partial} | {a.errors} | "
            f"{notable} |"
        )
    lines.append("")

    # By source.
    if t.by_source:
        lines.append("## By source")
        lines.append("")
        lines.append("| Source | Queued | Skipped (catalog dedup) | Errors |")
        lines.append("| --- | ---: | ---: | ---: |")
        for source in sorted(t.by_source.keys()):
            s = t.by_source[source]
            lines.append(
                f"| {source} | {s.queued} | {s.skipped_catalog} | {s.errors} |"
            )
        lines.append("")

    # Token burn.
    lines.append("## Token burn")
    lines.append("")
    if not t.by_token_cell:
        lines.append(
            "_No LLM-driven agents emitted token records in this window "
            "(reviewer / curator agents land in Phase 8+)._"
        )
    else:
        lines.append("| Agent | Model | Runs | Input | Output | Cache R/W | Tool calls |")
        lines.append("| --- | --- | ---: | ---: | ---: | ---: | ---: |")
        for (agent, model) in sorted(t.by_token_cell.keys()):
            c = t.by_token_cell[(agent, model)]
            lines.append(
                f"| {agent} | {model} | {c.runs_with_tokens} | "
                f"{c.input_tokens} | {c.output_tokens} | "
                f"{c.cache_read_tokens}/{c.cache_write_tokens} | "
                f"{c.tool_calls} |"
            )
    lines.append("")

    # Triage.
    if t.triage:
        lines.append("## Things to triage")
        lines.append("")
        for item in t.triage[:20]:
            lines.append(f"- {item}")
        if len(t.triage) > 20:
            lines.append(f"- … and {len(t.triage) - 20} more")
        lines.append("")

    # Always end with a single trailing newline.
    return "\n".join(lines) + "\n"
