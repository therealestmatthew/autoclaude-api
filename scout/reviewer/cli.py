"""scout review — CLI entry point for the reviewer agent.

Wired into scout/agent/cli.py as the `review` subcommand.
"""

from __future__ import annotations

import argparse

from .runner import run_review


def add_review_subparser(sub: argparse._SubParsersAction) -> None:  # type: ignore[type-arg]
    """Register `scout review` under the existing argparse subparsers."""
    p = sub.add_parser(
        "review",
        help="Run the LLM reviewer agent over queue candidates.",
        description=(
            "Proposes keep/merge/discard for queue candidates via the Anthropic API. "
            "Proposals land in the 8.3 proposals table; the operator approves/rejects "
            "via the web UI. Requires ANTHROPIC_API_KEY and the web API to be running "
            "(except in --dry-run mode)."
        ),
    )
    p.add_argument(
        "--slug",
        dest="candidate_slugs",
        nargs="+",
        metavar="SLUG",
        help="Review specific candidate slugs (space-separated). Default: all.",
    )
    p.add_argument(
        "--limit", "-n",
        type=int,
        default=None,
        metavar="N",
        help="Cap the number of parent-level candidates reviewed per invocation.",
    )
    p.add_argument(
        "--budget",
        type=float,
        default=None,
        metavar="USD",
        help=(
            "Override the daily budget cap in USD. "
            "Default: FT_AUTOCLAUDE_REVIEWER_DAILY_BUDGET env var or $5.00."
        ),
    )
    p.add_argument(
        "--dry-run",
        action="store_true",
        help=(
            "Run the agent but don't write proposals or charge the budget. "
            "Logs decisions to stdout. Does not require the API server."
        ),
    )
    p.add_argument(
        "--model",
        choices=("sonnet", "opus"),
        default=None,
        help="Force a specific model. Default: sonnet (with opus escalation on low confidence).",
    )
    p.add_argument(
        "--api-url",
        default=None,
        metavar="URL",
        help="Base URL of the ft-autoclaude API (default: http://localhost:8000).",
    )
    p.add_argument(
        "--evals",
        action="store_true",
        help="Run the eval harness over the golden set instead of the live queue.",
    )
    p.add_argument("--verbose", "-v", action="store_true")


def handle_review(args: argparse.Namespace) -> int:
    """Dispatch the `review` subcommand."""
    if args.evals:
        from .eval import run_evals
        return run_evals(verbose=args.verbose)

    model_map = {
        "sonnet": "claude-sonnet-4-6",
        "opus": "claude-opus-4-7",
    }
    force_model = model_map.get(args.model) if args.model else None
    default_model = "claude-sonnet-4-6"

    kwargs: dict = dict(
        limit=args.limit,
        candidate_slugs=args.candidate_slugs,
        dry_run=args.dry_run,
        verbose=args.verbose,
        budget_cap=args.budget,
        model=default_model,
        force_model=force_model,
    )
    if args.api_url:
        kwargs["api_url"] = args.api_url

    stats = run_review(**kwargs)

    prefix = "[dry-run] " if stats["dry_run"] else ""
    print(
        f"{prefix}{stats['run_id']}: "
        f"processed={stats['processed']} "
        f"proposed={stats['proposed']} "
        f"keep={stats['action_counts'].get('keep', 0)} "
        f"merge={stats['action_counts'].get('merge', 0)} "
        f"discard={stats['action_counts'].get('discard', 0)} "
        f"cost=${stats['total_cost_usd']:.4f}"
    )
    if stats["errors"]:
        import sys
        for e in stats["errors"]:
            print(f"  ! {e['slug']}: {e['error']}", file=sys.stderr)
        return 1
    return 0
