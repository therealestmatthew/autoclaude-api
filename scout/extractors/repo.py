"""Repo extractor: turn a scouted GitHub repo into child Candidates.

The extractor is queue-driven (the runner invokes it on queue entries whose
`source.type` is `github` and `kind` is `repo`) and manually-triggerable via
`scout extract-repo`.

Flow per repo:

  1. Run scout-clone-runner in a sandboxed container, capture its tar stdout.
  2. Extract the tar into a host-side `TemporaryDirectory()`.
  3. Re-validate every extracted path against the allowlist and reject any
     symlink escape (defense in depth — container is the boundary, host is
     the second line).
  4. Walk the tree; detect children per `_DETECTORS`; emit one Candidate per
     match with `parent: <repo-slug>` and `fingerprint: sha256:<hex>`.
  5. Yield Candidates back to the caller.

Failure modes are listed in /docs/plans/phase-4-repo-extractor.md. The
extractor records non-fatal warnings on a returned `RepoExtractReport`; the
runner threads them into the per-run stats / thread log.
"""

from __future__ import annotations

import hashlib
import json
import re
import tarfile
from collections.abc import Callable, Iterator
from dataclasses import dataclass, field
from datetime import date
from io import BytesIO
from pathlib import Path
from tempfile import TemporaryDirectory
from urllib.parse import urlsplit

from .._container import ContainerError, run_clone_container
from .._security import sanitize_text
from .._util import parse_frontmatter
from ..agent.types import Candidate, RepoExtractRequest

# ---------------------------------------------------------------------------
# Path allowlist + detectors
# ---------------------------------------------------------------------------

# Allowlist applied on **host-side** extraction. Mirrors the container's
# allowlist; never trust the container's output blindly.
_ALLOWED_TOP_FILES = {"mcp.json", ".scout-manifest.json"}
_ALLOWED_TOP_PATTERNS = (
    re.compile(r"^README"),
    re.compile(r"^LICENSE"),
    re.compile(r".*\.md$"),
)
_ALLOWED_DIRS = (".claude/", "agents/", "skills/", "prompts/")


def _is_allowed_relpath(rel: str) -> bool:
    """Host-side check that mirrors the container's allowlist."""
    if "/" not in rel:
        if rel in _ALLOWED_TOP_FILES:
            return True
        return any(p.match(rel) for p in _ALLOWED_TOP_PATTERNS)
    return rel.startswith(_ALLOWED_DIRS)


# ---------------------------------------------------------------------------
# Detection table
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class _Detected:
    kind: str                    # agent | skill | plugin | mcp | prompt
    child_name: str              # the <child-name> piece of <repo>--<child-name>
    title: str
    body_path: Path              # the file whose bytes are hashed for fingerprint
    extra: dict = field(default_factory=dict)


def _detect_children(root: Path, manifest: dict) -> Iterator[_Detected]:
    """Yield `_Detected` per child found under `root` (the extracted clone).

    Rules are evaluated in priority order. The first matching rule for a
    given file wins; subsequent rules don't double-emit.
    """
    seen_files: set[Path] = set()

    # 1. .claude/agents/**/*.md → agent
    for path in sorted(root.glob(".claude/agents/**/*.md")):
        if path in seen_files or not path.is_file():
            continue
        seen_files.add(path)
        yield _agent_from_md(path)

    # 2. .claude/skills/**/SKILL.md → skill (one per containing directory)
    for path in sorted(root.glob(".claude/skills/**/SKILL.md")):
        if path in seen_files or not path.is_file():
            continue
        seen_files.add(path)
        yield _skill_from_skill_md(path)

    # 3. .claude/plugins/**/plugin.json → plugin
    for path in sorted(root.glob(".claude/plugins/**/plugin.json")):
        if path in seen_files or not path.is_file():
            continue
        seen_files.add(path)
        d = _plugin_from_json(path)
        if d is not None:
            yield d

    # 4. mcp.json (.claude/ or top-level) → one Candidate per server entry
    for candidate_path in (root / ".claude" / "mcp.json", root / "mcp.json"):
        if candidate_path in seen_files or not candidate_path.is_file():
            continue
        seen_files.add(candidate_path)
        yield from _mcp_from_json(candidate_path)

    # 5. skills/**/SKILL.md → skill (non-namespaced)
    for path in sorted(root.glob("skills/**/SKILL.md")):
        if path in seen_files or not path.is_file():
            continue
        seen_files.add(path)
        yield _skill_from_skill_md(path)

    # 6. agents/**/*.md → agent (non-namespaced)
    for path in sorted(root.glob("agents/**/*.md")):
        if path in seen_files or not path.is_file():
            continue
        seen_files.add(path)
        yield _agent_from_md(path)

    # 7. prompts/**/*.md → prompt (only when frontmatter declares it)
    for path in sorted(root.glob("prompts/**/*.md")):
        if path in seen_files or not path.is_file():
            continue
        seen_files.add(path)
        d = _prompt_from_md(path)
        if d is not None:
            yield d


def _title_from_frontmatter_or_h1(path: Path, fallback: str) -> str:
    text = _safe_read_text(path)
    fm = parse_frontmatter(text)
    title = fm.get("title") if isinstance(fm, dict) else None
    if isinstance(title, str) and title.strip():
        return title.strip()
    for line in text.splitlines():
        s = line.strip()
        if s.startswith("# "):
            return s[2:].strip()
    return fallback


def _safe_read_text(path: Path) -> str:
    return path.read_text(encoding="utf-8", errors="replace")


def _agent_from_md(path: Path) -> _Detected:
    child = path.stem
    title = _title_from_frontmatter_or_h1(path, child)
    return _Detected(kind="agent", child_name=child, title=title, body_path=path)


def _skill_from_skill_md(path: Path) -> _Detected:
    child = path.parent.name
    title = _title_from_frontmatter_or_h1(path, child)
    return _Detected(kind="skill", child_name=child, title=title, body_path=path)


def _plugin_from_json(path: Path) -> _Detected | None:
    try:
        data = json.loads(_safe_read_text(path))
    except json.JSONDecodeError:
        return None
    if not isinstance(data, dict):
        return None
    child = path.parent.name
    title = sanitize_text(data.get("displayName") or data.get("name") or child, max_length=300)
    return _Detected(kind="plugin", child_name=child, title=title, body_path=path)


def _mcp_from_json(path: Path) -> Iterator[_Detected]:
    """Emit one Candidate per server entry in `mcpServers` (Claude Code shape).

    Falls back to one Candidate per file if no servers map is recognized.
    """
    try:
        data = json.loads(_safe_read_text(path))
    except json.JSONDecodeError:
        return
    servers = data.get("mcpServers") if isinstance(data, dict) else None
    if isinstance(servers, dict) and servers:
        for name in sorted(servers.keys()):
            slug_name = f"mcp-{_kebab(name)}"
            yield _Detected(
                kind="mcp",
                child_name=slug_name,
                title=sanitize_text(name, max_length=300),
                body_path=path,
            )
        return
    # Generic mcp.json — emit one Candidate for the file as a whole.
    yield _Detected(kind="mcp", child_name="mcp", title="MCP config", body_path=path)


def _prompt_from_md(path: Path) -> _Detected | None:
    """Conservative: only emit if the frontmatter declares it a prompt."""
    text = _safe_read_text(path)
    fm = parse_frontmatter(text)
    if not isinstance(fm, dict):
        return None
    if fm.get("kind") != "prompt" and "purpose" not in fm:
        return None
    child = path.stem
    title = _title_from_frontmatter_or_h1(path, child)
    return _Detected(kind="prompt", child_name=child, title=title, body_path=path)


_NON_KEBAB = re.compile(r"[^a-z0-9]+")


def _kebab(name: str) -> str:
    return _NON_KEBAB.sub("-", name.lower()).strip("-") or "unnamed"


# ---------------------------------------------------------------------------
# Tar extraction (with host-side re-validation)
# ---------------------------------------------------------------------------

class SymlinkEscape(Exception):
    """Raised when the container's tar contains a symlink — even one that
    appears to stay within the clone. Mirrors the container's policy."""


def _extract_tar_safely(tar_bytes: bytes, dest: Path) -> tuple[list[str], dict]:
    """Extract `tar_bytes` into `dest`, re-validating allowlist + symlinks.

    Returns `(extracted_relpaths, manifest_dict)`. Raises `SymlinkEscape` on
    any symlink. Files outside the allowlist are silently skipped (defense in
    depth — the container should have already filtered them).
    """
    extracted: list[str] = []
    manifest: dict = {}
    dest_resolved = dest.resolve()

    with tarfile.open(fileobj=BytesIO(tar_bytes), mode="r") as tf:
        for member in tf:
            # No symlinks, no hardlinks, no devices. Anything weird → bail.
            if member.issym() or member.islnk() or member.isdev():
                raise SymlinkEscape(f"tar member {member.name!r} is a link or device")
            if not member.isfile():
                continue
            rel = member.name.removeprefix("./")
            if not _is_allowed_relpath(rel):
                continue

            target = (dest / rel).resolve()
            # Guard against ../ traversal even though tarfile usually catches it.
            if dest_resolved not in target.parents and target != dest_resolved:
                raise SymlinkEscape(f"tar member {member.name!r} escapes clone root")

            target.parent.mkdir(parents=True, exist_ok=True)
            extracted_obj = tf.extractfile(member)
            if extracted_obj is None:
                continue
            target.write_bytes(extracted_obj.read())
            extracted.append(rel)

    manifest_path = dest / ".scout-manifest.json"
    if manifest_path.exists():
        try:
            manifest = json.loads(manifest_path.read_text())
        except json.JSONDecodeError:
            manifest = {}

    return extracted, manifest


# ---------------------------------------------------------------------------
# RepoExtractor
# ---------------------------------------------------------------------------

@dataclass
class RepoExtractReport:
    """Non-fatal observations the runner threads into the run record."""

    candidates: list[Candidate] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    extracted_files: int = 0
    commit_sha: str = ""


# Type for an injectable "get the tar bytes" function. Production passes
# `run_clone_container`; tests inject a stub.
TarFetcher = Callable[[str], bytes]


class RepoExtractor:
    type = "repo"

    def __init__(
        self,
        fetch_tar: TarFetcher | None = None,
        *,
        runtime: str = "docker",
    ) -> None:
        self._runtime = runtime
        self._fetch_tar = fetch_tar or self._default_fetch_tar

    def _default_fetch_tar(self, repo_url: str) -> bytes:
        return run_clone_container(repo_url, runtime=self._runtime).stdout

    def extract(self, req: RepoExtractRequest) -> RepoExtractReport:
        """Run end-to-end extraction for one repo and return a report."""
        report = RepoExtractReport()

        try:
            tar_bytes = self._fetch_tar(req.repo_url)
        except ContainerError as e:
            report.warnings.append(f"container-error: {e}")
            return report

        with TemporaryDirectory(prefix="scout-clone-") as tmp:
            root = Path(tmp)
            try:
                extracted, manifest = _extract_tar_safely(tar_bytes, root)
            except SymlinkEscape as e:
                report.warnings.append(f"security-event:symlink-escape: {e}")
                return report
            except tarfile.TarError as e:
                report.warnings.append(f"tar-error: {e}")
                return report

            report.extracted_files = len(extracted)
            report.commit_sha = str(manifest.get("commit_sha", ""))

            # Bubble up the container's own warnings (if any) on the report.
            container_warnings = manifest.get("warnings") or []
            if isinstance(container_warnings, list):
                for w in container_warnings:
                    if isinstance(w, str):
                        report.warnings.append(f"container:{w}")

            # File fingerprints from the manifest (we trust the container's
            # sha256 only enough to skip re-hashing identical bytes; if a
            # file is missing from the manifest we compute on the host).
            sha_by_relpath: dict[str, str] = {}
            for entry in manifest.get("files") or []:
                if not isinstance(entry, dict):
                    continue
                rel = entry.get("relpath")
                sha = entry.get("sha256")
                if isinstance(rel, str) and isinstance(sha, str):
                    sha_by_relpath[rel] = sha

            seen_slugs: set[str] = set()
            today = date.today().isoformat()
            org_repo = _org_repo_from_url(req.repo_url)

            for det in _detect_children(root, manifest):
                rel = str(det.body_path.relative_to(root))
                child_slug = f"{req.repo_slug}--{det.child_name}"
                if child_slug in seen_slugs:
                    report.warnings.append(
                        f"duplicate-child-slug: {child_slug} "
                        f"(second match at {rel}; emitted first only)"
                    )
                    continue
                seen_slugs.add(child_slug)

                sha = sha_by_relpath.get(rel) or _sha256_file(det.body_path)
                blob_url = _github_blob_url(org_repo, report.commit_sha, rel) or req.repo_url

                report.candidates.append(
                    Candidate(
                        name=child_slug,
                        kind=det.kind,  # type: ignore[arg-type]
                        title=sanitize_text(det.title, max_length=300),
                        source_type="github",
                        source_url=blob_url,
                        source_authors=list(req.source_authors),
                        source_license=req.source_license,
                        discovered_via=req.discovered_via,
                        discovered_on=today,
                        run_id=req.run_id,
                        raw_url=req.repo_url,
                        parent=req.repo_slug,
                        fingerprint=f"sha256:{sha}",
                    )
                )

        return report


# ---------------------------------------------------------------------------
# Small helpers
# ---------------------------------------------------------------------------

def _sha256_file(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


_GITHUB_HOST = "github.com"


def _org_repo_from_url(url: str) -> tuple[str, str] | None:
    parts = urlsplit(url)
    if parts.hostname != _GITHUB_HOST:
        return None
    segs = [s for s in parts.path.split("/") if s]
    if len(segs) < 2:
        return None
    repo = segs[1]
    if repo.endswith(".git"):
        repo = repo[:-4]
    return segs[0], repo


def _github_blob_url(org_repo: tuple[str, str] | None, sha: str, relpath: str) -> str | None:
    if org_repo is None or not sha:
        return None
    org, repo = org_repo
    return f"https://github.com/{org}/{repo}/blob/{sha}/{relpath}"
