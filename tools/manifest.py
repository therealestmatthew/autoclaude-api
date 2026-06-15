"""Repository manifest scanner.

Walks `git ls-files`, parses YAML frontmatter from markdown documents and
`<path>.meta.yaml` sidecars from binary documents, and emits MANIFEST.md at
the repo root.

See conventions/frontmatter.md for the rules this scanner enforces.

CLI:
    uv run manifest                     # write MANIFEST.md
    uv run manifest --stdout            # markdown to stdout
    uv run manifest --json              # JSON records to stdout
    uv run manifest --check             # exit non-zero if any issues
"""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
from collections.abc import Iterable
from dataclasses import asdict, dataclass, field
from datetime import UTC, datetime
from pathlib import Path

import yaml

REPO_ROOT = Path(__file__).resolve().parents[1]
MANIFEST_PATH = REPO_ROOT / "MANIFEST.md"

MARKDOWN_EXTENSIONS = {".md", ".markdown"}
BINARY_DOCUMENT_EXTENSIONS = {
    ".pdf", ".docx", ".pptx", ".xlsx", ".doc", ".ppt", ".xls",
    ".png", ".jpg", ".jpeg", ".gif", ".svg", ".webp",
    ".zip", ".tar", ".gz",
    ".csv", ".tsv",
    ".mp3", ".mp4", ".wav", ".webm",
}
SIDECAR_SUFFIX = ".meta.yaml"

# Status values allowed per kind. Mirror of conventions/frontmatter.md.
_CATALOG_STATUSES = {"draft", "reviewed", "adopted", "archived"}
ALLOWED_STATUS_BY_KIND: dict[str, set[str]] = {
    "agent":       _CATALOG_STATUSES,
    "skill":       _CATALOG_STATUSES,
    "plugin":      _CATALOG_STATUSES,
    "mcp":         _CATALOG_STATUSES,
    "prompt":      _CATALOG_STATUSES,
    "repo":        _CATALOG_STATUSES,
    "article":     _CATALOG_STATUSES,
    "person":      _CATALOG_STATUSES,
    "org":         _CATALOG_STATUSES,
    "engagement":  {"prospecting", "active", "paused", "completed"},
    "methodology": {"draft", "active", "retired"},
    "template":    {"draft", "active", "retired"},
    "plan":           {"draft", "active", "done", "superseded"},
    "session-prompt": {"draft", "active", "done", "superseded"},
    "runbook":        {"draft", "active", "stale", "retired"},
    "convention":  {"draft", "active", "retired"},
    "readme":      {"active", "stub", "retired"},
    "generated":   {"active", "stale"},
}

REQUIRED_FIELDS = ("name", "title", "status", "updated_at")


@dataclass
class DocumentRecord:
    path: str
    fm_source: str = "missing"       # 'inline' | 'sidecar' | 'missing'
    kind: str = ""
    name: str = ""
    title: str = ""
    status: str = ""
    updated_at: str = ""
    has_frontmatter: bool = False
    issues: list[str] = field(default_factory=list)


def git_tracked_files(root: Path = REPO_ROOT) -> list[Path]:
    """Enumerate files tracked by git, returned as absolute paths."""
    result = subprocess.run(
        ["git", "-C", str(root), "ls-files"],
        check=True, capture_output=True, text=True,
    )
    return [root / line for line in result.stdout.splitlines() if line]


def parse_frontmatter(path: Path) -> dict | None:
    """Parse YAML frontmatter from the head of a markdown file.

    Returns the parsed dict if a `---`-delimited block is present at the top,
    None otherwise.
    """
    try:
        text = path.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return None
    if not text.startswith("---"):
        return None
    # Skip the opening "---\n" then find the closing "\n---" (start of line).
    end_idx = text.find("\n---", 4)
    if end_idx == -1:
        return None
    raw = text[4:end_idx]
    try:
        loaded = yaml.safe_load(raw)
    except yaml.YAMLError:
        return None
    return loaded if isinstance(loaded, dict) else None


def parse_sidecar(binary_path: Path) -> dict | None:
    """Look for `<path>.meta.yaml` next to a binary file and parse it."""
    sidecar = binary_path.with_name(binary_path.name + SIDECAR_SUFFIX)
    if not sidecar.exists():
        return None
    try:
        loaded = yaml.safe_load(sidecar.read_text(encoding="utf-8"))
    except (OSError, yaml.YAMLError):
        return None
    return loaded if isinstance(loaded, dict) else None


def validate(fm: dict | None) -> list[str]:
    """Return a list of issues describing what's missing or wrong."""
    if fm is None:
        return ["missing-frontmatter"]
    issues: list[str] = []
    for f in REQUIRED_FIELDS:
        if not fm.get(f):
            issues.append(f"missing-field:{f}")
    kind = fm.get("kind", "")
    status = fm.get("status", "")
    if (
        kind and kind in ALLOWED_STATUS_BY_KIND
        and status and status not in ALLOWED_STATUS_BY_KIND[kind]
    ):
        issues.append(f"invalid-status:{status}-for-{kind}")
    return issues


def _record_from(path_rel: str, fm: dict | None, source: str) -> DocumentRecord:
    fm = fm or {}
    rec = DocumentRecord(
        path=path_rel,
        fm_source=source if fm else "missing",
        kind=str(fm.get("kind", "")),
        name=str(fm.get("name", "")),
        title=str(fm.get("title", "")),
        status=str(fm.get("status", "")),
        updated_at=str(fm.get("updated_at", "")),
        has_frontmatter=bool(fm),
    )
    rec.issues = validate(fm if fm else None)
    return rec


def scan(files: Iterable[Path] | None = None) -> list[DocumentRecord]:
    """Scan tracked files; produce one DocumentRecord per recognised document."""
    if files is None:
        files = git_tracked_files()
    records: list[DocumentRecord] = []
    for abs_path in files:
        try:
            rel = abs_path.relative_to(REPO_ROOT)
        except ValueError:
            rel = abs_path
        rel_str = str(rel)
        if rel_str.endswith(SIDECAR_SUFFIX):
            continue  # sidecars are consumed when scanning their parent
        ext = abs_path.suffix.lower()
        if ext in MARKDOWN_EXTENSIONS:
            records.append(_record_from(rel_str, parse_frontmatter(abs_path), "inline"))
        elif ext in BINARY_DOCUMENT_EXTENSIONS:
            records.append(_record_from(rel_str, parse_sidecar(abs_path), "sidecar"))
    return records


def render_markdown(records: list[DocumentRecord]) -> str:
    now = datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%SZ")
    total = len(records)
    by_status: dict[str, int] = {}
    by_kind: dict[str, int] = {}
    by_dir: dict[str, list[DocumentRecord]] = {}
    missing = 0
    with_issues = 0
    for r in records:
        by_status[r.status or "-"] = by_status.get(r.status or "-", 0) + 1
        by_kind[r.kind or "-"] = by_kind.get(r.kind or "-", 0) + 1
        top = r.path.split("/", 1)[0] if "/" in r.path else "(root)"
        by_dir.setdefault(top, []).append(r)
        if not r.has_frontmatter:
            missing += 1
        if r.issues:
            with_issues += 1

    lines: list[str] = [
        "---",
        "name: manifest",
        'title: "Repository manifest"',
        "kind: generated",
        "status: active",
        "generated_by: tools/manifest.py",
        f"generated_at: {now}",
        f"updated_at: {now[:10]}",
        "---",
        "",
        "# Repository manifest",
        "",
        "Generated by `uv run manifest`. Lists every tracked document, its "
        "frontmatter (or sidecar for binary documents), and any validation "
        "issues per `conventions/frontmatter.md`. Do not edit by hand — "
        "regenerate.",
        "",
        "## Summary",
        "",
        f"- Documents scanned: **{total}**",
        f"- Missing frontmatter / sidecar: **{missing}**",
        f"- With validation issues: **{with_issues}**",
        "",
        "### By kind",
        "",
        "| Kind | Count |",
        "| --- | ---:|",
    ]
    for k in sorted(by_kind):
        lines.append(f"| `{k}` | {by_kind[k]} |")
    lines += ["", "### By status", "", "| Status | Count |", "| --- | ---:|"]
    for s in sorted(by_status):
        lines.append(f"| `{s}` | {by_status[s]} |")
    lines += ["", "## Documents", ""]
    for top in sorted(by_dir):
        header = f"### `/{top}/`" if top != "(root)" else "### (root)"
        lines += [header, ""]
        lines += [
            "| Path | Kind | Name | Title | Status | Updated | Issues |",
            "| --- | --- | --- | --- | --- | --- | --- |",
        ]
        for r in sorted(by_dir[top], key=lambda x: x.path):
            issues = "; ".join(r.issues) if r.issues else ""
            title = (r.title or "").replace("|", "\\|")
            lines.append(
                f"| `{r.path}` | `{r.kind or '-'}` | `{r.name or '-'}` | "
                f"{title or '-'} | `{r.status or '-'}` | "
                f"{r.updated_at or '-'} | {issues} |"
            )
        lines.append("")
    return "\n".join(lines) + "\n"


def render_json(records: list[DocumentRecord]) -> str:
    return json.dumps([asdict(r) for r in records], indent=2, default=str) + "\n"


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="manifest",
        description="Scan repo documents and generate MANIFEST.md.",
    )
    parser.add_argument(
        "--check", action="store_true",
        help="Exit non-zero if any document has issues (missing frontmatter, "
             "missing required fields, invalid status).",
    )
    parser.add_argument(
        "--json", action="store_true",
        help="Emit JSON to stdout instead of writing MANIFEST.md.",
    )
    parser.add_argument(
        "--stdout", action="store_true",
        help="Emit markdown to stdout instead of writing MANIFEST.md.",
    )
    args = parser.parse_args(argv)

    records = scan()

    if args.json:
        sys.stdout.write(render_json(records))
    elif args.stdout:
        sys.stdout.write(render_markdown(records))
    else:
        MANIFEST_PATH.write_text(render_markdown(records), encoding="utf-8")
        print(f"wrote {MANIFEST_PATH.relative_to(REPO_ROOT)} ({len(records)} documents)")

    if args.check:
        bad = [r for r in records if r.issues]
        if bad:
            print(f"\n{len(bad)} document(s) with issues:", file=sys.stderr)
            for r in bad:
                print(f"  {r.path}: {'; '.join(r.issues)}", file=sys.stderr)
            return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
