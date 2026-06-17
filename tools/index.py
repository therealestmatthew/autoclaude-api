"""Entry point for `uv run autoclaude-index`.

Subcommands:

    autoclaude-index sync                # walk repo, drain into DB
    autoclaude-index sync --verbose
    autoclaude-index status              # print IndexMeta + counts
    autoclaude-index upgrade             # alembic upgrade head
    autoclaude-index reset [--yes]       # drop tables + upgrade + sync
"""

from __future__ import annotations

import argparse
import sys

from alembic import command
from alembic.config import Config
from sqlalchemy import select

from web.apps.api.db import (
    IndexMeta,
    SyncResult,
    make_engine,
    make_session_factory,
    migrations_dir,
    resolve_dsn,
    sync,
)
from web.apps.api.db.models import Asset, Base
from web.apps.api.indexer import Indexer
from web.apps.api.settings import get_settings


def _alembic_config(dsn: str) -> Config:
    cfg = Config(str(migrations_dir() / "alembic.ini"))
    cfg.set_main_option("script_location", str(migrations_dir()))
    cfg.set_main_option("sqlalchemy.url", dsn)
    return cfg


def _cmd_upgrade(args: argparse.Namespace) -> int:
    settings = get_settings()
    dsn = resolve_dsn(settings.repo_root)
    command.upgrade(_alembic_config(dsn), "head")
    print(f"upgraded {dsn} -> head", file=sys.stderr)
    return 0


def _cmd_sync(args: argparse.Namespace) -> int:
    settings = get_settings()
    dsn = resolve_dsn(settings.repo_root)
    engine = make_engine(dsn)
    factory = make_session_factory(engine)
    indexer = Indexer(settings.repo_root)
    result: SyncResult = sync(indexer, factory)
    print(_format_sync_result(result), file=sys.stderr)
    if args.verbose:
        print(f"  dsn          {dsn}", file=sys.stderr)
        print(f"  repo_root    {result.repo_root}", file=sys.stderr)
    return 0


def _cmd_status(args: argparse.Namespace) -> int:
    settings = get_settings()
    dsn = resolve_dsn(settings.repo_root)
    engine = make_engine(dsn)
    factory = make_session_factory(engine)
    with factory() as session:
        meta = session.get(IndexMeta, 1)
        count = session.execute(select(Asset)).scalars().all()
    if meta is None:
        print("no sync has run yet — try `autoclaude-index sync`", file=sys.stderr)
        return 0
    print("autoclaude index status", file=sys.stderr)
    print(f"  dsn               {dsn}", file=sys.stderr)
    print(f"  repo_root         {meta.repo_root}", file=sys.stderr)
    print(f"  schema_version    {meta.schema_version}", file=sys.stderr)
    print(f"  last_sync_at      {meta.last_sync_at:.0f}", file=sys.stderr)
    print(f"  last_sync_run_id  {meta.last_sync_run_id}", file=sys.stderr)
    print(f"  records (meta)    {meta.last_sync_record_count}", file=sys.stderr)
    print(f"  records (now)     {len(count)}", file=sys.stderr)
    return 0


def _cmd_reset(args: argparse.Namespace) -> int:
    if not args.yes:
        print("`reset` drops every table. Pass --yes to confirm.", file=sys.stderr)
        return 2
    settings = get_settings()
    dsn = resolve_dsn(settings.repo_root)
    engine = make_engine(dsn)
    Base.metadata.drop_all(engine)
    # Also drop the alembic_version table so the upgrade below starts fresh.
    with engine.begin() as conn:
        conn.exec_driver_sql("DROP TABLE IF EXISTS alembic_version")
    command.upgrade(_alembic_config(dsn), "head")
    factory = make_session_factory(engine)
    indexer = Indexer(settings.repo_root)
    result = sync(indexer, factory)
    print(_format_sync_result(result), file=sys.stderr)
    return 0


def _format_sync_result(result: SyncResult) -> str:
    return (
        f"sync ok — run_id={result.run_id} "
        f"records={result.records} "
        f"written={result.rows_written} "
        f"skipped={result.rows_skipped} "
        f"deleted={result.rows_deleted} "
        f"({result.duration_seconds:.2f}s)"
    )


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="autoclaude-index",
        description="Persistent index for the autoclaude web command center.",
    )
    sub = parser.add_subparsers(dest="cmd", required=True)

    p_sync = sub.add_parser("sync", help="walk the repo and drain into the DB")
    p_sync.add_argument("-v", "--verbose", action="store_true")
    p_sync.set_defaults(func=_cmd_sync)

    p_status = sub.add_parser("status", help="print current sync state")
    p_status.set_defaults(func=_cmd_status)

    p_upgrade = sub.add_parser("upgrade", help="run alembic upgrade head")
    p_upgrade.set_defaults(func=_cmd_upgrade)

    p_reset = sub.add_parser(
        "reset", help="drop all tables, re-migrate, and sync from scratch"
    )
    p_reset.add_argument("--yes", action="store_true", help="confirm destructive op")
    p_reset.set_defaults(func=_cmd_reset)

    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    return args.func(args)


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
