"""Static export: package the catalog as a downloadable browser-friendly bundle.

Walks the repo with the same `Indexer` the FastAPI backend uses, applies the
filter rules from `export.config.yaml` (or `--config <path>`), writes JSON
data files into `web/apps/web/public/data/`, copies the raw `.md` files for
download, then drives the Next.js static export (`next build` with
`output: 'export'`).

The result is a self-contained directory that can be unzipped and hosted on
any static file server (S3, Cloudflare Pages, Vercel) — or even opened from
the local filesystem with a small static server.

Usage:
    uv run ft-autoclaude-export-static
    uv run ft-autoclaude-export-static --out dist/catalog
    uv run ft-autoclaude-export-static --config profiles/client-share.yaml
    uv run ft-autoclaude-export-static --no-build       # data export only
"""
from __future__ import annotations

import argparse
import datetime as _dt
import json
import os
import shutil
import subprocess
import sys
from dataclasses import dataclass, field
from pathlib import Path

import yaml

from web.apps.api.indexer import AssetRecord, Indexer


class _Encoder(json.JSONEncoder):
    """Handles `datetime.date` values that PyYAML returns from frontmatter."""

    def default(self, o):
        if isinstance(o, (_dt.date, _dt.datetime)):
            return o.isoformat()
        return super().default(o)


def _project_root() -> Path:
    return Path(__file__).resolve().parents[1]


def _web_root() -> Path:
    return _project_root() / "web" / "apps" / "web"


# ---------------------------------------------------------------------------
# Filter configuration
# ---------------------------------------------------------------------------


@dataclass
class FilterConfig:
    """Driven by `export.config.yaml`. Empty lists mean 'no restriction'."""

    status: list[str] = field(default_factory=list)
    kind: list[str] = field(default_factory=list)
    delivery_function: list[str] = field(default_factory=list)
    tags: list[str] = field(default_factory=list)

    exclude_slugs: set[str] = field(default_factory=set)
    include_slugs: set[str] = field(default_factory=set)

    include_conventions: bool = True
    include_plans: bool = False

    @classmethod
    def from_dict(cls, data: dict | None) -> "FilterConfig":
        if not data:
            return cls()
        include = data.get("include") or {}
        return cls(
            status=list(include.get("status") or []),
            kind=list(include.get("kind") or []),
            delivery_function=list(include.get("delivery_function") or []),
            tags=list(include.get("tags") or []),
            exclude_slugs=set(data.get("exclude_slugs") or []),
            include_slugs=set(data.get("include_slugs") or []),
            include_conventions=bool(data.get("include_conventions", True)),
            include_plans=bool(data.get("include_plans", False)),
        )

    def passes(self, rec: AssetRecord) -> bool:
        """Apply the include rules to a single catalog record."""
        if rec.slug in self.exclude_slugs:
            return False
        if rec.slug in self.include_slugs:
            return True
        if self.status and rec.status not in self.status:
            return False
        if self.kind and rec.kind not in self.kind:
            return False
        if self.delivery_function:
            if not any(fn in self.delivery_function for fn in rec.delivery_functions):
                return False
        if self.tags:
            if not any(t in self.tags for t in rec.tags):
                return False
        return True


def load_config(path: Path | None) -> FilterConfig:
    """Load filter config from a YAML file; return defaults if missing."""
    if path is None:
        path = _project_root() / "export.config.yaml"
    if not path.is_file():
        return FilterConfig()
    raw = yaml.safe_load(path.read_text(encoding="utf-8"))
    return FilterConfig.from_dict(raw if isinstance(raw, dict) else None)


# ---------------------------------------------------------------------------
# Wire shapes (mirror api/models.py)
# ---------------------------------------------------------------------------


def _record_to_summary(rec: AssetRecord) -> dict:
    return {
        "path": rec.path,
        "bucket": rec.bucket,
        "slug": rec.slug,
        "kind": rec.kind,
        "title": rec.title,
        "status": rec.status,
        "quality": rec.quality,
        "tags": list(rec.tags),
        "delivery_functions": list(rec.delivery_functions),
        "created_at": rec.created_at,
        "updated_at": rec.updated_at,
        "issues": list(rec.issues),
        "version": rec.raw_hash,
    }


def _record_to_detail(rec: AssetRecord) -> dict:
    detail = _record_to_summary(rec)
    detail.update(
        body=rec.body,
        source=rec.source,
        discovered=rec.discovered,
        relations=rec.relations,
    )
    return detail


def _write_json(path: Path, data: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(data, indent=2, sort_keys=False, ensure_ascii=False, cls=_Encoder),
        encoding="utf-8",
    )


# ---------------------------------------------------------------------------
# Data export
# ---------------------------------------------------------------------------


def export_data(
    repo_root: Path,
    web_root: Path,
    config: FilterConfig,
    verbose: bool = False,
) -> dict:
    """Walk the repo, apply the filter, and write the JSON + raw bundle."""
    data_dir = web_root / "public" / "data"
    raw_dir = data_dir / "raw"

    if data_dir.exists():
        shutil.rmtree(data_dir)
    data_dir.mkdir(parents=True, exist_ok=True)
    raw_dir.mkdir(parents=True, exist_ok=True)

    indexer = Indexer(repo_root)
    snapshot = indexer.scan()

    # Partition by bucket.
    by_bucket: dict[str, list[AssetRecord]] = {}
    for rec in snapshot.records:
        by_bucket.setdefault(rec.bucket, []).append(rec)

    # Apply the filter to catalog records only — conventions/plans are
    # gated by the whole-section toggles.
    raw_catalog = by_bucket.get("catalog", [])
    catalog_records = [r for r in raw_catalog if config.passes(r)]
    filtered_out = len(raw_catalog) - len(catalog_records)

    _write_json(
        data_dir / "catalog.json",
        {
            "items": [_record_to_summary(r) for r in catalog_records],
            "total": len(catalog_records),
        },
    )

    # Decide which buckets get a detail file written.
    detail_buckets: set[str] = {"catalog"}
    if config.include_conventions:
        detail_buckets.add("convention")
    if config.include_plans:
        detail_buckets.add("plan")

    # Track the slugs that make it into the bundle. The Next.js
    # `generateStaticParams` for the catalog detail route reads this index.
    included_slugs: set[str] = {r.slug for r in catalog_records}

    detail_count = 0
    for rec in snapshot.records:
        if rec.bucket not in detail_buckets:
            continue
        if rec.bucket == "catalog" and rec.slug not in included_slugs:
            continue  # excluded by the filter
        _write_json(data_dir / "assets" / f"{rec.slug}.json", _record_to_detail(rec))
        src = repo_root / rec.path
        if src.is_file():
            dest = raw_dir / f"{rec.slug}.md"
            shutil.copyfile(src, dest)
        detail_count += 1

    # Conventions / plans summary lists. Empty if their section toggle is off.
    convention_items = by_bucket.get("convention", []) if config.include_conventions else []
    plan_items = by_bucket.get("plan", []) if config.include_plans else []
    _write_json(
        data_dir / "conventions.json",
        {"items": [_record_to_summary(r) for r in convention_items], "total": len(convention_items)},
    )
    _write_json(
        data_dir / "plans.json",
        {"items": [_record_to_summary(r) for r in plan_items], "total": len(plan_items)},
    )

    # Slug index for `generateStaticParams`.
    slug_index: dict[str, dict] = {}
    for rec in catalog_records:
        slug_index[rec.slug] = {"bucket": rec.bucket, "path": rec.path, "kind": rec.kind}
    for rec in convention_items:
        slug_index[rec.slug] = {"bucket": rec.bucket, "path": rec.path, "kind": rec.kind}
    for rec in plan_items:
        slug_index[rec.slug] = {"bucket": rec.bucket, "path": rec.path, "kind": rec.kind}
    _write_json(data_dir / "slug-index.json", slug_index)

    manifest = {
        "exported_at_mtime_ceiling": snapshot.scan_mtime_ceiling,
        "repo_root": snapshot.repo_root,
        "filter": {
            "status": config.status,
            "kind": config.kind,
            "delivery_function": config.delivery_function,
            "tags": config.tags,
            "exclude_slugs": sorted(config.exclude_slugs),
            "include_slugs": sorted(config.include_slugs),
            "include_conventions": config.include_conventions,
            "include_plans": config.include_plans,
        },
        "counts": {
            "catalog_included": len(catalog_records),
            "catalog_filtered_out": filtered_out,
            "details_written": detail_count,
            "conventions": len(convention_items),
            "plans": len(plan_items),
        },
    }
    _write_json(data_dir / "manifest.json", manifest)

    if verbose:
        print(f"  catalog included      : {len(catalog_records)}")
        print(f"  catalog filtered out  : {filtered_out}")
        print(f"  conventions           : {len(convention_items)}")
        print(f"  plans                 : {len(plan_items)}")
        print(f"  detail files written  : {detail_count}")
        print(f"  raw .md files copied  : {len(list(raw_dir.glob('*.md')))}")

    return manifest


# ---------------------------------------------------------------------------
# Next.js build orchestration
# ---------------------------------------------------------------------------


def run_next_build(web_root: Path, verbose: bool = False) -> None:
    env = os.environ.copy()
    env["NEXT_PUBLIC_STATIC_MODE"] = "true"
    cmd = ["npm", "run", "build"]
    if verbose:
        print(f"\n→ running {' '.join(cmd)} in {web_root} (NEXT_PUBLIC_STATIC_MODE=true)")
    result = subprocess.run(cmd, cwd=web_root, env=env)
    if result.returncode != 0:
        sys.exit(f"next build failed with exit code {result.returncode}")


def collect_output(web_root: Path, out_dir: Path, verbose: bool = False) -> Path:
    src = web_root / "out"
    if not src.is_dir():
        sys.exit(f"expected static export at {src} but it doesn't exist")
    if out_dir.exists():
        shutil.rmtree(out_dir)
    shutil.copytree(src, out_dir)
    if verbose:
        print(f"\n→ deliverable written to {out_dir}")
    return out_dir


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--out",
        default="dist/catalog-static",
        help="Output directory for the static bundle (default: dist/catalog-static)",
    )
    parser.add_argument(
        "--config",
        default=None,
        help="Path to a filter config YAML (default: export.config.yaml at repo root)",
    )
    parser.add_argument(
        "--no-build",
        action="store_true",
        help="Only export data into public/data/; skip the Next.js build",
    )
    parser.add_argument("-v", "--verbose", action="store_true")
    args = parser.parse_args()

    repo_root = _project_root()
    web_root = _web_root()
    out_dir = (Path.cwd() / args.out).resolve()
    config_path = Path(args.config).resolve() if args.config else None
    config = load_config(config_path)

    if args.verbose:
        print(f"repo root : {repo_root}")
        print(f"web root  : {web_root}")
        print(f"out dir   : {out_dir}")
        print(f"config    : {config_path or (repo_root / 'export.config.yaml')}\n")

    print("→ exporting data bundle…")
    manifest = export_data(repo_root, web_root, config, verbose=args.verbose)
    if not args.verbose:
        c = manifest["counts"]
        print(
            f"  included={c['catalog_included']}  "
            f"excluded={c['catalog_filtered_out']}  "
            f"details={c['details_written']}"
        )

    if args.no_build:
        print("\n--no-build set; data export complete.")
        return

    run_next_build(web_root, verbose=args.verbose)
    collect_output(web_root, out_dir, verbose=args.verbose)
    print(f"\n✓ static bundle ready at {out_dir}")
    print("  Serve with any static file server, e.g.:")
    print(f"    python -m http.server -d {out_dir} 8080")


if __name__ == "__main__":
    main()
