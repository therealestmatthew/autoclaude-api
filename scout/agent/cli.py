"""Scout CLI entry point.

  scout run                       # single tick across all enabled sources
  scout run --source <slug>       # single source by slug (filename stem)
  scout run --no-dedup            # skip the post-tick dedup pass
  scout run --no-check-urls       # skip the URL-liveness tail step
  scout run -v                    # verbose
  scout extract-repo <url|slug>   # one-shot manual extraction of one repo
  scout extract-repo --podman <…> # podman stub (raises NotImplementedError)
  scout dedup                     # run all four dedup passes once
  scout dedup --pass <name>       # one pass: identity|url|proposals|archive
  scout dedup --dry-run           # report what would change; touch nothing
  scout check-urls                # HEAD catalog URLs; write liveness state
  scout check-urls --since <date> # skip URLs last_checked on/after this date
  scout check-urls --all          # no per-run URL cap
  scout report                    # today's rollup, printed
  scout report --week             # last 7 days
  scout report --since <date>     # custom range
  scout report --write            # also write to /command-center/token-burn/reports/
  scout doctor                    # catalog integrity checks
  scout doctor --json             # machine-readable
  scout doctor --fix              # auto-fix slug↔filename mismatches only
  scout doctor --strict           # exit nonzero on any finding
"""

from __future__ import annotations

import argparse
import json
import sys
from datetime import date, timedelta
from pathlib import Path

from ..doctor import run_checks
from ..liveness import check_urls_once
from ..liveness.check import LIVENESS_STATE_FILENAME
from ..report import aggregate, render
from .runner import (
    CATALOG_DIR,
    STATE_DIR,
    THREADS_DIR,
    dedup_once,
    extract_repo_once,
    run_once,
)

REPORTS_DIR = Path(__file__).resolve().parents[2] / "command-center" / "token-burn" / "reports"
QUEUE_DIR = Path(__file__).resolve().parents[2] / "scout" / "queue"


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="scout", description="autoclaude scout agent")
    sub = parser.add_subparsers(dest="cmd", required=True)

    run_p = sub.add_parser("run", help="Run the scout once over enabled sources.")
    run_p.add_argument(
        "--source", "-s",
        help="Only run this source (matches /scout/sources/<slug>.yaml).",
    )
    run_p.add_argument("--verbose", "-v", action="store_true")
    run_p.add_argument(
        "--no-dedup",
        action="store_true",
        help="Skip the post-tick dedup pass (normally runs after extractors).",
    )
    run_p.add_argument(
        "--no-check-urls",
        action="store_true",
        help="Skip the URL-liveness tail step.",
    )

    ex_p = sub.add_parser(
        "extract-repo",
        help="Manually extract child assets from one GitHub repo.",
    )
    ex_p.add_argument(
        "target",
        help="A GitHub URL (https://github.com/<org>/<repo>) or an <org>/<repo> shortcut.",
    )
    ex_p.add_argument(
        "--runtime", default="docker", choices=("docker", "podman"),
        help="Container runtime. v1 default is docker; podman is a stub.",
    )
    ex_p.add_argument("--verbose", "-v", action="store_true")

    dedup_p = sub.add_parser(
        "dedup",
        help="Run the dedup engine over /scout/queue and /catalog.",
    )
    dedup_p.add_argument(
        "--pass",
        dest="only_pass",
        choices=("identity", "url", "proposals", "archive"),
        help="Run a single pass instead of all four (debugging).",
    )
    dedup_p.add_argument(
        "--dry-run",
        action="store_true",
        help="Compute what would change; do not write anything to disk.",
    )
    dedup_p.add_argument("--verbose", "-v", action="store_true")

    cu_p = sub.add_parser(
        "check-urls",
        help="HEAD every catalog source.url; update liveness state file.",
    )
    cu_p.add_argument(
        "--since",
        help="Skip URLs whose last_check is on or after this ISO date.",
    )
    cu_p.add_argument(
        "--all",
        action="store_true",
        help="No per-run URL cap. Default caps at 50.",
    )
    cu_p.add_argument("--verbose", "-v", action="store_true")

    rep_p = sub.add_parser(
        "report",
        help="Aggregate thread logs into a markdown rollup.",
    )
    rep_p.add_argument(
        "--week", action="store_true",
        help="Last 7 days instead of today.",
    )
    rep_p.add_argument(
        "--since",
        help="Custom window start (ISO date). Window ends today.",
    )
    rep_p.add_argument(
        "--write", action="store_true",
        help="Also write the report to /command-center/token-burn/reports/.",
    )

    doc_p = sub.add_parser(
        "doctor",
        help="Static integrity checks over /catalog/.",
    )
    doc_p.add_argument(
        "--json", action="store_true",
        help="Machine-readable output.",
    )
    doc_p.add_argument(
        "--fix", action="store_true",
        help="Auto-fix slug↔filename mismatches (only).",
    )
    doc_p.add_argument(
        "--strict", action="store_true",
        help="Exit nonzero if any finding is reported.",
    )

    args = parser.parse_args(argv)

    if args.cmd == "run":
        stats = run_once(
            source_name=args.source,
            verbose=args.verbose,
            run_dedup=not args.no_dedup,
            run_liveness=not args.no_check_urls,
        )
        print(
            f"{stats['run_id']}: "
            f"queued={stats['candidates_queued']} "
            f"skipped_catalog={stats['candidates_skipped_catalog_dedup']} "
            f"errors={len(stats['errors'])}"
        )
        if stats["errors"]:
            for e in stats["errors"]:
                print(f"  ! {e}", file=sys.stderr)
            return 1
        return 0

    if args.cmd == "extract-repo":
        repo_url = _normalize_repo_target(args.target)
        result = extract_repo_once(
            repo_url=repo_url,
            runtime=args.runtime,
            verbose=args.verbose,
        )
        print(
            f"{result['run_id']}: "
            f"children_queued={result['children_queued']} "
            f"warnings={len(result['warnings'])}"
        )
        for w in result["warnings"]:
            print(f"  ! {w}", file=sys.stderr)
        return 0 if not result["fatal"] else 1

    if args.cmd == "dedup":
        record = dedup_once(
            only_pass=args.only_pass,
            dry_run=args.dry_run,
            verbose=args.verbose,
        )
        tag = "[dry-run] " if args.dry_run else ""
        print(f"{tag}{record['thread_id']}: {record['summary']}")
        if record["errors"]:
            for e in record["errors"]:
                print(f"  ! {e}", file=sys.stderr)
        return 0

    if args.cmd == "check-urls":
        since = _parse_iso_date(args.since) if args.since else None
        max_urls = None if args.all else 50
        stats = check_urls_once(
            CATALOG_DIR,
            STATE_DIR / LIVENESS_STATE_FILENAME,
            since=since,
            max_urls=max_urls,
            verbose=args.verbose,
        )
        print(
            f"liveness: checked={stats['checked']}/{stats['total_urls']} "
            f"ok={stats['ok']} 4xx={stats['error_4xx']} 5xx={stats['error_5xx']} "
            f"net_err={stats['network_errors']} unsafe={stats['unsafe']} "
            f"throttled={stats['skipped_throttle']}"
        )
        return 0

    if args.cmd == "report":
        today = date.today()
        if args.since:
            start = _parse_iso_date(args.since)
        elif args.week:
            start = today - timedelta(days=6)
        else:
            start = today
        totals = aggregate(
            sorted(THREADS_DIR.glob("*.jsonl")) if THREADS_DIR.exists() else [],
            period_start=start,
            period_end=today,
        )
        md = render(totals)
        sys.stdout.write(md)
        if args.write:
            REPORTS_DIR.mkdir(parents=True, exist_ok=True)
            if start == today:
                fname = f"{today.isoformat()}.md"
            else:
                fname = f"{start.isoformat()}-week.md" if args.week else (
                    f"{start.isoformat()}-{today.isoformat()}.md"
                )
            (REPORTS_DIR / fname).write_text(md)
            print(f"\n[wrote {REPORTS_DIR / fname}]", file=sys.stderr)
        return 0

    if args.cmd == "doctor":
        report = run_checks(CATALOG_DIR, QUEUE_DIR, fix=args.fix)
        if args.json:
            print(json.dumps({
                "findings": [f.to_dict() for f in report.findings],
                "fixes_applied": report.fixes_applied,
                "summary": report.by_kind(),
            }, indent=2))
        else:
            summary = report.by_kind()
            if not summary:
                print("doctor: 0 findings")
            else:
                parts = ", ".join(f"{k}={v}" for k, v in sorted(summary.items()))
                print(f"doctor: {parts}")
                for f in report.findings:
                    print(f"  {f.kind}: {f.asset} — {f.detail}")
            if report.fixes_applied:
                print("Fixes applied:")
                for fx in report.fixes_applied:
                    print(f"  {fx}")
        return 1 if (args.strict and report.findings) else 0

    return 2


def _parse_iso_date(s: str) -> date:
    try:
        return date.fromisoformat(s)
    except ValueError as e:
        raise SystemExit(f"invalid ISO date: {s!r}") from e


def _normalize_repo_target(target: str) -> str:
    """Accept `https://github.com/<org>/<repo>` or `<org>/<repo>` shortcut."""
    if target.startswith(("http://", "https://")):
        return target
    if "/" in target and " " not in target:
        return f"https://github.com/{target.strip('/')}"
    raise SystemExit(f"unrecognized repo target: {target!r}")


if __name__ == "__main__":
    raise SystemExit(main())
