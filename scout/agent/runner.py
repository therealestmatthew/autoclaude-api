"""Scout runner: orchestration loop tying sources, extractors, state, and queue.

Single pass `run_once` per the agent README:
  1. Load enabled sources from /scout/sources/*.yaml
  2. For each, load state, dispatch to the matching extractor.
  3. Dedup each Candidate against the existing /catalog/ (exact + canonical URL).
  4. Write surviving candidates to /scout/queue/<date>-<slug>-<hash>.md.
  5. Persist state and write a thread record to /command-center/threads/<date>.jsonl.

Resist building a "platform" here. Kept under ~150 lines on purpose.
"""

from __future__ import annotations

import hashlib
import json
from datetime import UTC, date, datetime
from pathlib import Path

import yaml

from .._util import canonical_github_url, parse_frontmatter, slugify
from ..extractors.awesome_list import AwesomeListExtractor
from ..extractors.hackernews import HackerNewsExtractor
from ..extractors.lobsters import LobstersExtractor
from ..extractors.reddit import RedditExtractor
from ..extractors.repo import RepoExtractor
from .types import (
    AwesomeListSource,
    Candidate,
    HackerNewsSource,
    LobstersSource,
    RedditSource,
    RepoExtractRequest,
    SourceState,
)

REPO_ROOT = Path(__file__).resolve().parents[2]
SOURCES_DIR = REPO_ROOT / "scout" / "sources"
STATE_DIR = REPO_ROOT / "scout" / "state"
QUEUE_DIR = REPO_ROOT / "scout" / "queue"
CATALOG_DIR = REPO_ROOT / "catalog"
THREADS_DIR = REPO_ROOT / "command-center" / "threads"


# One entry per supported source `type:`. New extractors register here.
EXTRACTOR_REGISTRY: dict[str, object] = {
    "awesome-list": AwesomeListExtractor(),
    "hackernews": HackerNewsExtractor(),
    "lobsters": LobstersExtractor(),
    "reddit": RedditExtractor(),
}

# How to parse a source config of a given type into its pydantic model.
SOURCE_MODELS: dict[str, type] = {
    "awesome-list": AwesomeListSource,
    "hackernews": HackerNewsSource,
    "lobsters": LobstersSource,
    "reddit": RedditSource,
}


def run_once(source_name: str | None = None, verbose: bool = False) -> dict:
    """Run a single tick across all enabled sources (or just one).

    Returns a stats dict suitable for the thread log.
    """
    started_at = datetime.now(UTC).isoformat()
    run_id = (
        "scout-"
        + date.today().isoformat()
        + "-"
        + datetime.now(UTC).strftime("%H%M%S")
    )

    catalog_urls = _existing_catalog_urls()
    if verbose:
        print(f"[scout] {len(catalog_urls)} URLs known to catalog")

    stats: dict = {
        "run_id": run_id,
        "started_at": started_at,
        "sources_run": [],
        "candidates_queued": 0,
        "candidates_skipped_catalog_dedup": 0,
        "errors": [],
    }

    source_files = sorted(SOURCES_DIR.glob("*.yaml"))
    if source_name:
        source_files = [s for s in source_files if s.stem == source_name]

    for src_path in source_files:
        cfg = yaml.safe_load(src_path.read_text())
        if not cfg.get("enabled", True):
            if verbose:
                print(f"[scout] skipping disabled source: {cfg.get('name')}")
            continue

        src_type = cfg.get("type")
        extractor = EXTRACTOR_REGISTRY.get(src_type)
        model = SOURCE_MODELS.get(src_type)
        if extractor is None or model is None:
            stats["errors"].append(
                {"source": cfg.get("name"), "error": f"no extractor for type {src_type!r}"}
            )
            continue

        source_obj = model.model_validate(cfg)
        state = _load_state(source_obj.name)
        state.last_run_at = started_at

        per_source = {"source": source_obj.name, "queued": 0, "skipped_catalog_dedup": 0}

        for cand in extractor.fetch(source_obj, state, run_id):
            canonical = canonical_github_url(cand.source_url)
            if cand.source_url in catalog_urls or canonical in catalog_urls:
                per_source["skipped_catalog_dedup"] += 1
                continue
            QUEUE_DIR.mkdir(parents=True, exist_ok=True)
            queue_path = QUEUE_DIR / _queue_filename(cand)
            queue_path.write_text(_candidate_to_markdown(cand))
            per_source["queued"] += 1

        # Cumulative state stats
        state.stats["runs"] = state.stats.get("runs", 0) + 1
        state.stats["candidates_queued_total"] = (
            state.stats.get("candidates_queued_total", 0) + per_source["queued"]
        )
        _save_state(state)

        stats["sources_run"].append(per_source)
        stats["candidates_queued"] += per_source["queued"]
        stats["candidates_skipped_catalog_dedup"] += per_source["skipped_catalog_dedup"]
        if verbose:
            print(
                f"[scout] {source_obj.name}: "
                f"queued={per_source['queued']} "
                f"skipped_catalog={per_source['skipped_catalog_dedup']}"
            )

    # After primary extractors, walk the queue for github-typed `repo` entries
    # and run the repo extractor over them. Children land back in /scout/queue/.
    repo_stats = _process_repo_queue(run_id=run_id, verbose=verbose)
    stats["repo_extraction"] = repo_stats
    stats["candidates_queued"] += repo_stats["children_queued"]

    stats["ended_at"] = datetime.now(UTC).isoformat()
    _write_thread_log(stats)
    return stats


def extract_repo_once(
    repo_url: str,
    *,
    runtime: str = "docker",
    verbose: bool = False,
    extractor: RepoExtractor | None = None,
) -> dict:
    """One-shot manual extraction. Mirrors the surface of `run_once` so the
    CLI can hand-off cleanly."""
    started_at = datetime.now(UTC).isoformat()
    run_id = (
        "scout-extract-"
        + date.today().isoformat()
        + "-"
        + datetime.now(UTC).strftime("%H%M%S")
    )

    repo_slug = slugify(canonical_github_url(repo_url).removeprefix("https://github.com/"))
    req = RepoExtractRequest(
        repo_slug=repo_slug,
        repo_url=repo_url,
        discovered_via="manual",
        run_id=run_id,
    )

    ext = extractor or RepoExtractor(runtime=runtime)
    report = ext.extract(req)

    written = 0
    for cand in report.candidates:
        QUEUE_DIR.mkdir(parents=True, exist_ok=True)
        (QUEUE_DIR / _queue_filename(cand)).write_text(_candidate_to_markdown(cand))
        written += 1

    if verbose:
        print(
            f"[scout] extract-repo {repo_slug}: "
            f"children_queued={written} warnings={len(report.warnings)} "
            f"extracted_files={report.extracted_files}"
        )

    record = {
        "run_id": run_id,
        "started_at": started_at,
        "ended_at": datetime.now(UTC).isoformat(),
        "repo_slug": repo_slug,
        "repo_url": repo_url,
        "children_queued": written,
        "warnings": report.warnings,
        "commit_sha": report.commit_sha,
        "fatal": bool(report.warnings) and written == 0,
    }
    _write_extract_thread_log(record)
    return record


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _load_state(source_name: str) -> SourceState:
    path = STATE_DIR / f"{source_name}.json"
    if path.exists():
        return SourceState.model_validate_json(path.read_text())
    return SourceState(source=source_name)


def _save_state(state: SourceState) -> None:
    STATE_DIR.mkdir(parents=True, exist_ok=True)
    path = STATE_DIR / f"{state.source}.json"
    path.write_text(state.model_dump_json(indent=2))


def _existing_catalog_urls() -> set[str]:
    """Walk /catalog/*.md (top level only) and collect source.url + canonical
    forms + all alternates.url, so the runner can dedup candidates against
    already-cataloged assets.
    """
    urls: set[str] = set()
    if not CATALOG_DIR.exists():
        return urls
    for md_path in CATALOG_DIR.glob("*.md"):
        fm = parse_frontmatter(md_path.read_text())
        src = fm.get("source")
        if not isinstance(src, dict):
            continue
        primary = src.get("url")
        if isinstance(primary, str) and primary:
            urls.add(primary)
            urls.add(canonical_github_url(primary))
        for alt in src.get("alternates") or []:
            if isinstance(alt, dict):
                u = alt.get("url")
                if isinstance(u, str) and u:
                    urls.add(u)
                    urls.add(canonical_github_url(u))
    return urls


def _queue_filename(c: Candidate) -> str:
    h = hashlib.sha256(c.source_url.encode("utf-8")).hexdigest()[:8]
    return f"{c.discovered_on}-{c.name}-{h}.md"


def _candidate_to_markdown(c: Candidate) -> str:
    fm: dict = {
        "name": c.name,
        "kind": c.kind,
        "title": c.title,
        "status": "draft",
        "tags": [],
        "source": {
            "type": c.source_type,
            "url": c.source_url,
            "authors": c.source_authors,
            "license": c.source_license,
        },
        "discovered": {
            "via": c.discovered_via,
            "on": c.discovered_on,
            "run_id": c.run_id,
        },
        "scout": {
            k: v for k, v in {
                "raw_title": c.raw_title,
                "raw_url": c.raw_url,
                "score": c.score,
                "excerpt": c.excerpt,
            }.items() if v is not None
        },
        "created_at": c.discovered_on,
        "updated_at": c.discovered_on,
    }
    if c.parent:
        fm["relations"] = {"parent": c.parent}
    if c.fingerprint:
        fm["fingerprint"] = c.fingerprint
    body = (
        "# Reviewer notes\n\n"
        "_Empty. Reviewer fills this in when deciding what to do with the candidate "
        "(see /conventions/merge-rules.md)._\n"
    )
    return f"---\n{yaml.safe_dump(fm, sort_keys=False, default_flow_style=False)}---\n\n{body}"


def _process_repo_queue(*, run_id: str, verbose: bool) -> dict:
    """Walk /scout/queue/ for unreviewed github-typed `kind: repo` entries and
    invoke the repo extractor on each. Children land back in the queue. The
    parent queue file is *not* removed — human review still decides whether
    the parent itself stays.

    To avoid re-extracting the same repo on every run, we skip any parent that
    already has at least one queue file with `relations.parent: <parent-slug>`.
    """
    if not QUEUE_DIR.exists():
        return {"repos_extracted": 0, "children_queued": 0, "warnings": []}

    parents_with_children: set[str] = set()
    repo_queue_paths: list[Path] = []
    for p in sorted(QUEUE_DIR.glob("*.md")):
        if p.name.startswith("_"):
            continue
        fm = parse_frontmatter(p.read_text())
        relations = fm.get("relations") if isinstance(fm, dict) else None
        if isinstance(relations, dict) and relations.get("parent"):
            parents_with_children.add(str(relations["parent"]))
            continue
        if fm.get("kind") != "repo":
            continue
        src = fm.get("source")
        if not isinstance(src, dict) or src.get("type") != "github":
            continue
        repo_queue_paths.append(p)

    extractor = RepoExtractor()
    repos_extracted = 0
    children_queued = 0
    warnings: list[str] = []

    for p in repo_queue_paths:
        fm = parse_frontmatter(p.read_text())
        repo_slug = fm.get("name")
        src = fm.get("source") or {}
        repo_url = src.get("url")
        if not (isinstance(repo_slug, str) and isinstance(repo_url, str)):
            continue
        if repo_slug in parents_with_children:
            continue

        discovered = fm.get("discovered") or {}
        req = RepoExtractRequest(
            repo_slug=repo_slug,
            repo_url=repo_url,
            discovered_via=str(discovered.get("via") or "manual"),
            run_id=run_id,
            source_authors=list(src.get("authors") or []),
            source_license=str(src.get("license") or ""),
        )
        report = extractor.extract(req)
        repos_extracted += 1

        for cand in report.candidates:
            (QUEUE_DIR / _queue_filename(cand)).write_text(_candidate_to_markdown(cand))
            children_queued += 1
        warnings.extend(report.warnings)
        if verbose:
            print(
                f"[scout] repo {repo_slug}: children_queued={len(report.candidates)} "
                f"warnings={len(report.warnings)}"
            )

    return {
        "repos_extracted": repos_extracted,
        "children_queued": children_queued,
        "warnings": warnings,
    }


def _write_extract_thread_log(record: dict) -> None:
    THREADS_DIR.mkdir(parents=True, exist_ok=True)
    today = date.today().isoformat()
    path = THREADS_DIR / f"{today}.jsonl"
    line = {
        "thread_id": record["run_id"],
        "agent": "scout-extract-repo",
        "started_at": record["started_at"],
        "ended_at": record["ended_at"],
        "outcome": "ok" if record["children_queued"] > 0 else "partial",
        "summary": (
            f"repo={record['repo_slug']} children={record['children_queued']} "
            f"warnings={len(record['warnings'])}"
        ),
        "stats": record,
    }
    with path.open("a") as f:
        f.write(json.dumps(line) + "\n")


def _write_thread_log(stats: dict) -> None:
    THREADS_DIR.mkdir(parents=True, exist_ok=True)
    today = date.today().isoformat()
    path = THREADS_DIR / f"{today}.jsonl"
    record = {
        "thread_id": stats["run_id"],
        "agent": "scout",
        "started_at": stats["started_at"],
        "ended_at": stats["ended_at"],
        "outcome": "ok" if not stats["errors"] else "partial",
        "summary": (
            f"queued={stats['candidates_queued']} "
            f"skipped_catalog={stats['candidates_skipped_catalog_dedup']} "
            f"errors={len(stats['errors'])}"
        ),
        "stats": stats,
    }
    with path.open("a") as f:
        f.write(json.dumps(record) + "\n")
