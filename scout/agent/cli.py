"""Scout CLI entry point.

  scout run                       # single tick across all enabled sources
  scout run --source <slug>       # single source by slug (filename stem)
  scout run -v                    # verbose
"""

from __future__ import annotations

import argparse
import sys

from .runner import run_once


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="scout", description="autoclaude scout agent")
    sub = parser.add_subparsers(dest="cmd", required=True)

    run_p = sub.add_parser("run", help="Run the scout once over enabled sources.")
    run_p.add_argument(
        "--source", "-s",
        help="Only run this source (matches /scout/sources/<slug>.yaml).",
    )
    run_p.add_argument("--verbose", "-v", action="store_true")

    args = parser.parse_args(argv)

    if args.cmd == "run":
        stats = run_once(source_name=args.source, verbose=args.verbose)
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

    return 2


if __name__ == "__main__":
    raise SystemExit(main())
