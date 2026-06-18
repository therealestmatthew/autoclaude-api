"""Queue triage primitives: keep / merge / discard.

These translate a queue candidate's frontmatter + body into the right
file operations and a single git commit.
"""

from __future__ import annotations

import contextlib
import logging
import threading
from dataclasses import dataclass, field
from datetime import date
from pathlib import Path
from typing import Any

from . import fs, git, serialize
from .editor import DirtyTree, VersionMismatch, _hash_text

_TRIAGE_LOCK = threading.Lock()
_log = logging.getLogger(__name__)


@dataclass(frozen=True)
class TriageResult:
    action: str                       # keep | merge | discard
    source_path: str                  # queue file path (relative)
    target_path: str | None           # catalog file path on keep/merge
    commit_sha: str
    new_version: str | None           # version of the catalog file post-write
    commit_created: bool              # True iff a new SHA was produced
    cascade: tuple = field(default_factory=tuple)
    # Each element is {"slug": str, "new_parent": str} for updated children.


def _read(p: Path) -> str:
    return p.read_text(encoding="utf-8") if p.is_file() else ""


def _cascade_parent_rename(
    repo_root: Path,
    old_slug: str,
    new_slug: str,
) -> list[dict[str, str]]:
    """Rewrite `relations.parent` from old_slug → new_slug in catalog files.

    Also rewrites queue files (no commit needed — they are gitignored). The
    cascade is best-effort: a malformed or dirty file is skipped with a warning.

    Returns a list of {slug, new_parent} for each catalog file committed.
    """
    cascaded: list[dict[str, str]] = []

    def _rewrite_file(md_file: Path, commit: bool) -> bool:
        try:
            text = md_file.read_text(encoding="utf-8")
        except OSError as e:
            _log.warning("cascade: could not read %s: %s", md_file, e)
            return False
        fm = serialize.parse_frontmatter(text)
        relations = fm.get("relations")
        if not isinstance(relations, dict):
            return False
        if relations.get("parent") != old_slug:
            return False
        relations["parent"] = new_slug
        fm["relations"] = relations
        new_text = serialize.replace_frontmatter(text, fm)
        try:
            fs.atomic_write(md_file, new_text)
        except Exception as e:
            _log.warning("cascade: could not write %s: %s", md_file, e)
            return False
        if commit:
            child_slug = md_file.stem
            msg = f"web: cascade parent rename {old_slug} -> {new_slug} ({child_slug})"
            try:
                git.commit(repo_root, paths=[md_file], message=msg, must_commit=True)
                return True
            except Exception as e:
                _log.warning("cascade: commit failed for %s: %s", md_file, e)
                return False
        return True

    # Catalog children — commit each one.
    catalog_dir = repo_root / "catalog"
    if catalog_dir.is_dir():
        for md_file in sorted(catalog_dir.glob("*.md")):
            if _rewrite_file(md_file, commit=True):
                cascaded.append({"slug": md_file.stem, "new_parent": new_slug})

    # Queue children — rewrite but no commit (gitignored).
    queue_dir = repo_root / "scout" / "queue"
    if queue_dir.is_dir():
        for md_file in sorted(queue_dir.glob("*.md")):
            _rewrite_file(md_file, commit=False)

    return cascaded


def _refuse_dirty(repo_root: Path, paths: list[Path]) -> None:
    rels = {
        str(p.resolve().relative_to(repo_root.resolve())) for p in paths
    }
    for line in git.status_porcelain(repo_root):
        changed = line[3:].strip()
        if changed in rels:
            raise DirtyTree(f"working tree already changed: {changed}")


def triage_keep(
    repo_root: Path,
    queue_rel: str,
    *,
    expected_version: str,
    target_slug: str | None = None,
    commit_message: str | None = None,
) -> TriageResult:
    """Promote a queue candidate to /catalog/.

    The frontmatter `status:` is flipped from `draft` → `reviewed`, the
    `updated_at` is bumped to today, the file is renamed under
    `catalog/`. If `target_slug` is provided (operator chose a rename),
    the destination filename and the `name:` field are updated.
    """
    with _TRIAGE_LOCK:
        source = fs.safe_path(repo_root, queue_rel)
        if not source.is_file():
            raise FileNotFoundError(queue_rel)
        source_text = _read(source)
        if _hash_text(source_text) != expected_version:
            raise VersionMismatch(
                current_version=_hash_text(source_text),
                expected_version=expected_version,
            )

        fm = serialize.parse_frontmatter(source_text)
        body = serialize.parse_body(source_text)
        # Capture the original queue slug BEFORE mutating fm.
        original_slug = fm.get("name") or source.stem
        chosen_slug = target_slug or original_slug
        # Bake the catalog frontmatter shape: status reviewed, updated_at
        # bumped, name set to chosen_slug.
        fm["name"] = chosen_slug
        fm["status"] = "reviewed"
        fm["updated_at"] = date.today().isoformat()
        # Tags must be a list; an empty tags is allowed.
        fm.setdefault("tags", [])

        dest_rel = f"catalog/{chosen_slug}.md"
        dest = fs.safe_path(repo_root, dest_rel)
        if dest.exists():
            raise FileExistsError(f"catalog target already exists: {dest_rel}")

        _refuse_dirty(repo_root, [source, dest])

        new_text = serialize.render_document(fm, body)
        fs.atomic_write(dest, new_text)
        fs.safe_delete(source, repo_root)
        stem = Path(queue_rel).stem
        message = (
            commit_message
            or f"web: triage keep {stem} -> catalog/{chosen_slug}"
        )
        try:
            sha, created = git.commit(
                repo_root,
                paths=[source, dest],
                message=message,
                must_commit=True,
            )
        except Exception:
            # Best-effort rollback: re-write the queue file and remove
            # the new catalog file. The audit log records what failed.
            try:
                fs.atomic_write(source, source_text)
                fs.safe_delete(dest, repo_root)
            except Exception:  # noqa: BLE001
                pass
            raise

        # If the operator renamed the candidate, rewrite any catalog/queue files
        # whose relations.parent pointed at the original slug. Each catalog child
        # gets its own commit; queue files are updated in place (gitignored).
        if target_slug and target_slug != original_slug:
            cascade = tuple(
                _cascade_parent_rename(repo_root, old_slug=original_slug, new_slug=target_slug)
            )
        else:
            cascade = ()

        return TriageResult(
            action="keep",
            source_path=queue_rel,
            target_path=dest_rel,
            commit_sha=sha,
            new_version=_hash_text(new_text),
            commit_created=created,
            cascade=cascade,
        )


_MERGE_SECTION_HEADER = "## From queue ({date})\n"


def triage_merge(
    repo_root: Path,
    queue_rel: str,
    *,
    target_slug: str,
    expected_version: str,
    commit_message: str | None = None,
) -> TriageResult:
    """Merge a queue candidate into an existing catalog asset.

    The candidate's body is appended as a `## From queue (<date>)` section.
    If the candidate's `source.url` differs from the target's, it lands in
    `target.source.alternates[]`. The queue file is deleted.
    """
    with _TRIAGE_LOCK:
        source = fs.safe_path(repo_root, queue_rel)
        target_rel = f"catalog/{target_slug}.md"
        target = fs.safe_path(repo_root, target_rel)
        if not source.is_file():
            raise FileNotFoundError(queue_rel)
        if not target.is_file():
            raise FileNotFoundError(target_rel)

        source_text = _read(source)
        if _hash_text(source_text) != expected_version:
            raise VersionMismatch(
                current_version=_hash_text(source_text),
                expected_version=expected_version,
            )
        target_text = _read(target)

        _refuse_dirty(repo_root, [source, target])

        cand_fm = serialize.parse_frontmatter(source_text)
        cand_body = serialize.parse_body(source_text).strip()
        target_fm = serialize.parse_frontmatter(target_text)
        target_body = serialize.parse_body(target_text).rstrip()

        # Append the candidate's body as a section. Stable header so a
        # second merge of the same source idempotently extends.
        date_str = date.today().isoformat()
        section = _MERGE_SECTION_HEADER.format(date=date_str)
        appended_body = (
            target_body
            + "\n\n"
            + section
            + "\n"
            + (cand_body or "_no body_")
            + "\n"
        )

        # Propagate the alternate URL.
        cand_source: dict[str, Any] = cand_fm.get("source") or {}
        target_source: dict[str, Any] = target_fm.setdefault("source", {})
        cand_url = cand_source.get("url")
        target_url = target_source.get("url")
        if cand_url and cand_url != target_url:
            alternates = list(target_source.get("alternates") or [])
            already = {a.get("url") for a in alternates if isinstance(a, dict)}
            if cand_url not in already:
                alternates.append(
                    {
                        "type": cand_source.get("type") or "article",
                        "url": cand_url,
                    }
                )
                target_source["alternates"] = alternates

        target_fm["updated_at"] = date_str

        new_text = serialize.render_document(target_fm, appended_body)
        fs.atomic_write(target, new_text)
        fs.safe_delete(source, repo_root)
        message = commit_message or f"web: triage merge {Path(queue_rel).stem} -> {target_slug}"
        try:
            sha, created = git.commit(
                repo_root,
                paths=[source, target],
                message=message,
                must_commit=True,
            )
        except Exception:
            try:
                fs.atomic_write(target, target_text)
                fs.atomic_write(source, source_text)
            except Exception:  # noqa: BLE001
                pass
            raise

        return TriageResult(
            action="merge",
            source_path=queue_rel,
            target_path=target_rel,
            commit_sha=sha,
            new_version=_hash_text(new_text),
            commit_created=created,
        )


def triage_discard(
    repo_root: Path,
    queue_rel: str,
    *,
    expected_version: str,
    notes: str,
    commit_message: str | None = None,
) -> TriageResult:
    """Delete a queue candidate. `notes` is required so the audit log
    captures why."""
    if not notes.strip():
        raise ValueError("triage discard requires a non-empty `notes` reason")
    with _TRIAGE_LOCK:
        source = fs.safe_path(repo_root, queue_rel)
        if not source.is_file():
            raise FileNotFoundError(queue_rel)
        source_text = _read(source)
        if _hash_text(source_text) != expected_version:
            raise VersionMismatch(
                current_version=_hash_text(source_text),
                expected_version=expected_version,
            )
        _refuse_dirty(repo_root, [source])

        fs.safe_delete(source, repo_root)
        message = commit_message or f"web: triage discard {Path(queue_rel).stem}"
        try:
            sha, created = git.commit(
                repo_root,
                paths=[source],
                message=message,
                must_commit=False,
            )
        except Exception:
            with contextlib.suppress(Exception):
                fs.atomic_write(source, source_text)
            raise
        return TriageResult(
            action="discard",
            source_path=queue_rel,
            target_path=None,
            commit_sha=sha,
            new_version=None,
            commit_created=created,
        )
