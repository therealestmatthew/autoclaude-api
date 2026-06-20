"""Batch reviewer runner.

Scans scout/queue/ for candidates, groups parent-child sets, calls the reviewer
agent on each, and writes proposals via the proposals API (or logs for --dry-run).

Idempotency: candidates with an existing pending proposal are skipped. The
operator must accept or reject the existing proposal before a new run will
replace it.

Budget: each call is charged against the daily cap before being made. The run
stops cleanly (exit 0) when the cap is hit — the operator can raise it and rerun.
"""

from __future__ import annotations

import os
from collections import defaultdict
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import httpx

from .._util import parse_frontmatter
from . import budget as _budget_mod
from .agent import ReviewerError, make_candidate_text, review_candidate
from .context import _split_body, get_context

REPO_ROOT = Path(__file__).resolve().parents[2]
_QUEUE_DIR = REPO_ROOT / "scout" / "queue"
_THREADS_DIR = REPO_ROOT / "command-center" / "threads"
_DEFAULT_API_URL = os.environ.get("FT_AUTOCLAUDE_API_URL", "http://localhost:8000")
_MAX_ESCALATION_RATE = 0.20


def _load_queue(queue_dir: Path) -> list[tuple[str, dict, str, Path]]:
    """Return (slug, frontmatter, body, path) for every queue candidate."""
    items = []
    for p in sorted(queue_dir.glob("*.md")):
        if p.name.startswith("_"):
            continue
        text = p.read_text()
        fm = parse_frontmatter(text)
        body = _split_body(text)
        slug = fm.get("slug") or p.stem
        items.append((slug, fm, body, p))
    return items


def _get_existing_proposals(api_url: str, target_path: str) -> list[dict]:
    """Query the API for existing proposals for this path. Returns [] on error."""
    try:
        r = httpx.get(
            f"{api_url}/proposals",
            params={"target_path": target_path, "status": "pending"},
            timeout=5.0,
        )
        if r.status_code == 200:
            return r.json().get("items", [])
    except Exception:
        pass
    return []


def _post_proposal(api_url: str, payload: dict) -> dict | None:
    """POST a proposal to the API. Returns the created proposal or None on error."""
    try:
        r = httpx.post(f"{api_url}/proposals", json=payload, timeout=10.0)
        if r.status_code == 201:
            return r.json()
        return None
    except Exception:
        return None


def _build_proposal_payload(
    slug: str,
    path: Path,
    decision: Any,
    model_used: str,
    group_members: list[str] | None = None,
    repo_root: Path = REPO_ROOT,
) -> dict:
    """Build the CreateProposalRequest dict from a Decision."""
    try:
        target_path = str(path.relative_to(repo_root))
    except ValueError:
        target_path = str(path)
    summary = decision.rationale.split(".")[0].strip()[:120]
    payload_data: dict[str, Any] = {
        "target_slug": decision.target_slug,
        "suggested_slug": decision.suggested_slug,
        "suggested_edits": decision.suggested_edits,
        "flags": decision.flags,
        "scope": decision.scope,
        "model": model_used,
    }
    if group_members:
        payload_data["group_members"] = group_members

    return {
        "source": "reviewer-agent",
        "target_path": target_path,
        "target_bucket": "queue",
        "action_kind": decision.action,
        "payload": {k: v for k, v in payload_data.items() if v is not None},
        "summary": summary,
        "rationale": decision.rationale,
        "confidence": decision.confidence,
    }


def run_review(
    *,
    limit: int | None = None,
    candidate_slugs: list[str] | None = None,
    dry_run: bool = False,
    verbose: bool = False,
    budget_cap: float | None = None,
    model: str = "claude-sonnet-4-6",
    force_model: str | None = None,
    api_url: str = _DEFAULT_API_URL,
    queue_dir: Path = _QUEUE_DIR,
    threads_dir: Path | None = None,
    repo_root: Path = REPO_ROOT,
) -> dict[str, Any]:
    """Run the reviewer over the queue. Returns a stats dict."""
    import anthropic

    api_key = os.environ.get("ANTHROPIC_API_KEY", "")
    if not api_key:
        raise SystemExit(
            "ANTHROPIC_API_KEY is not set. "
            "See /command-center/runbooks/scout-review.md for setup instructions."
        )

    client = anthropic.Anthropic(api_key=api_key)
    t_dir = threads_dir or _THREADS_DIR
    cap = budget_cap if budget_cap is not None else float(
        os.environ.get("FT_AUTOCLAUDE_REVIEWER_DAILY_BUDGET", "5.00")
    )
    budget = _budget_mod.check_budget(cap=cap, threads_dir=t_dir)

    if budget.will_exceed:
        raise SystemExit(
            f"Daily budget cap (${cap:.2f}) already reached "
            f"(spent: ${budget.spent_today_usd:.4f}). "
            f"Use --budget <N> to override."
        )

    # Load queue
    all_candidates = _load_queue(queue_dir)

    # Filter to requested slugs if given
    if candidate_slugs:
        slug_set = set(candidate_slugs)
        all_candidates = [(s, fm, b, p) for s, fm, b, p in all_candidates if s in slug_set]

    # Build parent→children map for grouping
    parent_map: dict[str, list[str]] = defaultdict(list)
    slug_to_item: dict[str, tuple[str, dict, str, Path]] = {}
    for item in all_candidates:
        slug, fm, body, path = item
        slug_to_item[slug] = item
        parent_slug = (fm.get("relations") or {}).get("parent")
        if parent_slug:
            parent_map[parent_slug].append(slug)

    # Build processing order: parents first, then orphans, skip children (handled via parent)
    processing_queue: list[tuple[str, list[str]]] = []  # (parent_slug, [child_slugs])
    seen_as_child: set[str] = set()
    for slug, fm, _body, _path in all_candidates:
        if slug in seen_as_child:
            continue
        children = parent_map.get(slug, [])
        # Check if this slug's parent is also in the queue (it's a child)
        own_parent = (fm.get("relations") or {}).get("parent")
        if own_parent and own_parent in slug_to_item:
            seen_as_child.add(slug)
            continue
        processing_queue.append((slug, children))
        seen_as_child.update(children)

    if limit:
        processing_queue = processing_queue[:limit]

    run_id = f"scout-reviewer-{datetime.now(UTC).strftime('%Y-%m-%d-%H%M%S')}"
    started_at = datetime.now(UTC).isoformat()

    stats: dict[str, Any] = {
        "run_id": run_id,
        "started_at": started_at,
        "processed": 0,
        "skipped_existing_proposal": 0,
        "skipped_budget": 0,
        "skipped_error": 0,
        "proposed": 0,
        "dry_run": dry_run,
        "escalations": 0,
        "action_counts": {"keep": 0, "merge": 0, "discard": 0},
        "total_input_tokens": 0,
        "total_output_tokens": 0,
        "total_cache_read_tokens": 0,
        "total_cache_write_tokens": 0,
        "total_cost_usd": 0.0,
        "errors": [],
    }

    for parent_slug, child_slugs in processing_queue:
        if parent_slug not in slug_to_item:
            continue
        _, fm, body, path = slug_to_item[parent_slug]
        try:
            target_path = str(path.relative_to(repo_root))
        except ValueError:
            target_path = str(path)

        # Skip if pending proposal exists
        if not dry_run:
            existing = _get_existing_proposals(api_url, target_path)
            if existing:
                if verbose:
                    print(f"  skip {parent_slug}: already has pending proposal")
                stats["skipped_existing_proposal"] += 1
                continue

        # Budget pre-check
        candidate_chars = len(body) + sum(
            len(slug_to_item[c][2]) for c in child_slugs if c in slug_to_item
        )
        estimated = _budget_mod.estimate_call_cost(force_model or model, candidate_chars + 500)
        budget = _budget_mod.check_budget(cap=cap, threads_dir=t_dir)
        if budget.spent_today_usd + estimated > cap:
            if verbose:
                print(f"  budget cap reached at {parent_slug}; stopping.")
            stats["skipped_budget"] += 1
            break

        # Fetch context
        tags = fm.get("tags") or []
        title = fm.get("title") or parent_slug
        context_items = get_context(title, tags)

        # Build candidate text (include children summary)
        child_slugs_in_queue = [c for c in child_slugs if c in slug_to_item]
        candidate_text = make_candidate_text(parent_slug, fm, body, child_slugs_in_queue or None)

        if verbose:
            scope = "parent-with-children" if child_slugs_in_queue else "self"
            print(f"  reviewing {parent_slug} [{scope}] ...")

        # Call the agent
        try:
            decision, usage, model_used = review_candidate(
                client=client,
                candidate_text=candidate_text,
                context_items=context_items,
                model=model,
                force_model=force_model,
            )
        except ReviewerError as exc:
            stats["errors"].append({"slug": parent_slug, "error": str(exc)})
            stats["skipped_error"] += 1
            if verbose:
                print(f"  ! error reviewing {parent_slug}: {exc}")
            continue

        # Tally usage
        call_cost = _budget_mod.token_cost(
            model=model_used,
            input_tokens=usage.get("input_tokens", 0),
            output_tokens=usage.get("output_tokens", 0),
            cache_read_tokens=usage.get("cache_read_tokens", 0),
            cache_write_tokens=usage.get("cache_write_tokens", 0),
        )
        stats["total_input_tokens"] += usage.get("input_tokens", 0)
        stats["total_output_tokens"] += usage.get("output_tokens", 0)
        stats["total_cache_read_tokens"] += usage.get("cache_read_tokens", 0)
        stats["total_cache_write_tokens"] += usage.get("cache_write_tokens", 0)
        stats["total_cost_usd"] += call_cost
        stats["processed"] += 1
        stats["action_counts"][decision.action] = stats["action_counts"].get(decision.action, 0) + 1
        if usage.get("escalated_from"):
            stats["escalations"] += 1

        if verbose:
            print(
                f"    → {decision.action} (confidence={decision.confidence:.2f}, "
                f"model={model_used}, cost=${call_cost:.4f})"
            )
            print(f"    rationale: {decision.rationale[:100]}...")

        # Write thread record for this call
        if not dry_run:
            _budget_mod.write_thread_record({
                "thread_id": run_id,
                "agent": "scout-reviewer",
                "started_at": started_at,
                "outcome": "ok",
                "summary": f"reviewed={parent_slug} action={decision.action}",
                "model": model_used,
                "input_tokens": usage.get("input_tokens", 0),
                "output_tokens": usage.get("output_tokens", 0),
                "cache_read_tokens": usage.get("cache_read_tokens", 0),
                "cache_write_tokens": usage.get("cache_write_tokens", 0),
            }, threads_dir=t_dir)

        if dry_run:
            continue

        # Determine all slugs to write proposals for
        targets: list[tuple[str, Path]] = [(parent_slug, path)]
        if child_slugs_in_queue:
            for c in child_slugs_in_queue:
                _, _, _, cp = slug_to_item[c]
                targets.append((c, cp))

        group_members = [t[0] for t in targets] if len(targets) > 1 else None

        for t_slug, t_path in targets:
            payload = _build_proposal_payload(
                slug=t_slug,
                path=t_path,
                decision=decision,
                model_used=model_used,
                group_members=group_members,
                repo_root=repo_root,
            )
            result = _post_proposal(api_url, payload)
            if result:
                stats["proposed"] += 1
                if verbose:
                    print(f"    posted proposal {result.get('id', '?')[:8]} for {t_slug}")
            else:
                stats["errors"].append({"slug": t_slug, "error": "proposal POST failed"})
                if verbose:
                    print(f"    ! POST failed for {t_slug}")

    # Write summary thread record
    ended_at = datetime.now(UTC).isoformat()
    stats["ended_at"] = ended_at
    if not dry_run:
        _budget_mod.write_thread_record({
            "thread_id": run_id,
            "agent": "scout-reviewer",
            "started_at": started_at,
            "ended_at": ended_at,
            "outcome": "ok" if not stats["errors"] else "partial",
            "summary": (
                f"processed={stats['processed']} "
                f"proposed={stats['proposed']} "
                f"escalations={stats['escalations']} "
                f"cost_usd={stats['total_cost_usd']:.4f}"
            ),
            "model": force_model or model,
            "input_tokens": stats["total_input_tokens"],
            "output_tokens": stats["total_output_tokens"],
            "cache_read_tokens": stats["total_cache_read_tokens"],
            "cache_write_tokens": stats["total_cache_write_tokens"],
        }, threads_dir=t_dir)

    if budget.near_cap and not dry_run:
        spent_pct = stats["total_cost_usd"] / cap * 100
        print(f"Warning: reviewer has spent ${stats['total_cost_usd']:.4f} "
              f"({spent_pct:.0f}% of ${cap:.2f} daily cap)")

    return stats
