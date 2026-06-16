"""Scout CLI entry point.

  scout run                       # single tick across all enabled sources
  scout run --source <slug>       # single source by slug (filename stem)
  scout run --no-dedup            # skip the post-tick dedup pass
  scout run -v                    # verbose
  scout extract-repo <url|slug>   # one-shot manual extraction of one repo
  scout extract-repo --podman <…> # podman stub (raises NotImplementedError)
  scout dedup                     # run all four dedup passes once
  scout dedup --pass <name>       # one pass: identity|url|proposals|archive
  scout dedup --dry-run           # report what would change; touch nothing
"""

from __future__ import annotations

import argparse
import sys

from .runner import dedup_once, extract_repo_once, run_once


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

    args = parser.parse_args(argv)

    if args.cmd == "run":
        stats = run_once(
            source_name=args.source,
            verbose=args.verbose,
            run_dedup=not args.no_dedup,
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

    return 2


def _normalize_repo_target(target: str) -> str:
    """Accept `https://github.com/<org>/<repo>` or `<org>/<repo>` shortcut."""
    if target.startswith(("http://", "https://")):
        return target
    if "/" in target and " " not in target:
        return f"https://github.com/{target.strip('/')}"
    raise SystemExit(f"unrecognized repo target: {target!r}")


if __name__ == "__main__":
    raise SystemExit(main())
