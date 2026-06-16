"""Catalog integrity checks.

Each check yields zero or more `Finding`s. None of them fail the run;
the CLI exit code is 0 unless `--strict` is passed.

Checks:

- **orphan-child** — asset with `relations.parent: <slug>` whose parent is
  neither in `/catalog/` nor `/scout/queue/`.
- **broken-supersedes** — `relations.supersedes: [<slug>]` where the
  named slug doesn't exist anywhere we can see.
- **slug-mismatch** — `name:` differs from the filename stem.
- **missing-required-field** — schema says required, frontmatter omits it.
- **stale-reviewed** — `status: reviewed`, no edits in >30 days. Not a bug;
  informational. Pass 4 of dedup is what actually decides auto-archive.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date
from pathlib import Path

from .._util import parse_frontmatter

_REQUIRED_FIELDS = ("name", "kind", "title", "status", "source", "discovered",
                    "created_at", "updated_at")
_STALE_DAYS = 30


@dataclass
class Finding:
    kind: str
    asset: str
    path: str
    detail: str

    def to_dict(self) -> dict:
        return {
            "kind": self.kind,
            "asset": self.asset,
            "path": self.path,
            "detail": self.detail,
        }


@dataclass
class DoctorReport:
    findings: list[Finding] = field(default_factory=list)
    fixes_applied: list[str] = field(default_factory=list)

    def by_kind(self) -> dict[str, int]:
        out: dict[str, int] = {}
        for f in self.findings:
            out[f.kind] = out.get(f.kind, 0) + 1
        return out


def run_checks(
    catalog_dir: Path,
    queue_dir: Path | None = None,
    *,
    today: date | None = None,
    fix: bool = False,
) -> DoctorReport:
    """Walk the catalog (and queue, for parent-resolution) and collect findings.

    With `fix=True` we additionally rename catalog files whose filename
    stem doesn't match the `name:` field. We only ever rename, never delete
    or rewrite contents — anything richer goes to a reviewer.
    """
    today = today or date.today()
    report = DoctorReport()

    if not catalog_dir.exists():
        return report

    catalog_files: dict[str, Path] = {}
    for p in sorted(catalog_dir.glob("*.md")):
        if p.name.startswith("_") or p.name == "README.md":
            continue
        catalog_files[p.stem] = p

    queue_slugs: set[str] = set()
    if queue_dir and queue_dir.exists():
        for q in queue_dir.glob("*.md"):
            if q.name.startswith("_") or q.name == "README.md":
                continue
            try:
                fm = parse_frontmatter(q.read_text())
            except OSError:
                continue
            name = fm.get("name") if isinstance(fm, dict) else None
            if isinstance(name, str):
                queue_slugs.add(name)

    catalog_slugs = set(catalog_files.keys())
    # We resolve parents/supersedes against either side.
    known_slugs = catalog_slugs | queue_slugs

    for stem, path in catalog_files.items():
        try:
            fm = parse_frontmatter(path.read_text())
        except OSError as e:
            report.findings.append(Finding(
                kind="unreadable",
                asset=stem,
                path=str(path),
                detail=str(e),
            ))
            continue
        if not isinstance(fm, dict):
            report.findings.append(Finding(
                kind="unparseable-frontmatter",
                asset=stem,
                path=str(path),
                detail="frontmatter did not parse as a mapping",
            ))
            continue

        name = fm.get("name")
        # Required fields.
        for f_name in _REQUIRED_FIELDS:
            if f_name not in fm or fm[f_name] in (None, "", [], {}):
                report.findings.append(Finding(
                    kind="missing-required-field",
                    asset=stem,
                    path=str(path),
                    detail=f"missing field: {f_name}",
                ))

        # Slug ↔ filename match.
        if isinstance(name, str) and name and name != stem:
            report.findings.append(Finding(
                kind="slug-mismatch",
                asset=name,
                path=str(path),
                detail=f"filename stem is {stem!r} but name: is {name!r}",
            ))
            if fix:
                # Only rename if the destination doesn't already exist.
                new_path = path.with_name(f"{name}.md")
                if not new_path.exists():
                    path.rename(new_path)
                    report.fixes_applied.append(
                        f"renamed {path.name} → {new_path.name}"
                    )

        # Orphan child.
        relations = fm.get("relations") if isinstance(fm.get("relations"), dict) else {}
        parent = relations.get("parent") if isinstance(relations, dict) else None
        if isinstance(parent, str) and parent and parent not in known_slugs:
            report.findings.append(Finding(
                kind="orphan-child",
                asset=stem,
                path=str(path),
                detail=f"parent {parent!r} not in catalog or queue",
            ))

        # Broken supersedes.
        supersedes = relations.get("supersedes") if isinstance(relations, dict) else []
        if isinstance(supersedes, list):
            for older in supersedes:
                if isinstance(older, str) and older not in known_slugs:
                    report.findings.append(Finding(
                        kind="broken-supersedes",
                        asset=stem,
                        path=str(path),
                        detail=f"supersedes {older!r} not in catalog or queue",
                    ))

        # Stale reviewed (informational).
        status = fm.get("status")
        updated = fm.get("updated_at")
        if status == "reviewed":
            updated_d = _parse_date(updated)
            if updated_d is not None and (today - updated_d).days > _STALE_DAYS:
                report.findings.append(Finding(
                    kind="stale-reviewed",
                    asset=stem,
                    path=str(path),
                    detail=(
                        f"status=reviewed, updated_at={updated_d.isoformat()} "
                        f"({(today - updated_d).days}d ago)"
                    ),
                ))

    return report


def _parse_date(v: object) -> date | None:
    from datetime import datetime
    if isinstance(v, date) and not isinstance(v, datetime):
        return v
    if isinstance(v, datetime):
        return v.date()
    if isinstance(v, str):
        try:
            return date.fromisoformat(v)
        except ValueError:
            return None
    return None
