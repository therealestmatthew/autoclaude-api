"""Four-pass dedup engine: identity, canonical-URL, soft-overlap, auto-archive.

The engine is a pure function of disk state. Run it twice in a row and the
second run produces identical state — that's the idempotency contract, and
the integration test enforces it.

Disk writes are limited to:
  - queue files (mergeset_id annotations, proposal body sections, deletion
    on identity / URL-canonical collapse)
  - catalog files (status, archived_reason, archived_at, updated_at — and
    NOTHING ELSE) on objective auto-archive
  - /scout/state/merge-decisions.json (rejected-proposals ledger)

Promotion to /catalog/ remains human-only forever. See
/docs/plans/phase-6-merge-dedup.md.
"""

from __future__ import annotations

import contextlib
import json
import re
from dataclasses import dataclass, field
from datetime import date
from pathlib import Path
from typing import Any

import yaml

from .._util import parse_frontmatter
from .archive import should_archive_for_404, should_archive_for_supersedes
from .fingerprint import canonical_url_key, fingerprint_key, slug_set_hash, url_key
from .overlap import jaccard, primary_author, title_tokens

JACCARD_THRESHOLD = 0.6
INTRA_PARENT_JACCARD = 0.9  # higher bar for two children of the same repo

# Body-section markers (HTML comments so they survive markdown renderers
# unchanged and are easy to find/replace deterministically).
COLLAPSE_START = "<!-- scout-dedup-collapse-start -->"
COLLAPSE_END = "<!-- scout-dedup-collapse-end -->"
PROPOSAL_START = "<!-- scout-dedup-proposal-start -->"
PROPOSAL_END = "<!-- scout-dedup-proposal-end -->"

PROPOSAL_HEADER = "## Merge proposal (auto)"
PROPOSAL_REJECTED_HEADER = "## Merge proposal (auto, rejected)"
COLLAPSE_HEADER = "## Collapsed (auto)"

# Catalog allowlist: the only frontmatter fields the engine may rewrite on
# an existing /catalog/ asset. Enforced inside `_apply_writes`.
CATALOG_ALLOWED_FIELDS = frozenset({"status", "archived_reason", "archived_at", "updated_at"})


@dataclass
class DedupReport:
    pass1_identity_collapse: int = 0
    pass2_url_canonicalize: int = 0
    pass3_merge_proposals: int = 0
    pass4_auto_archived: int = 0
    rejected_proposals_carried: int = 0
    errors: list[str] = field(default_factory=list)

    def summary(self) -> str:
        return (
            f"identity={self.pass1_identity_collapse} "
            f"url={self.pass2_url_canonicalize} "
            f"proposals={self.pass3_merge_proposals} "
            f"auto_archived={self.pass4_auto_archived}"
        )


@dataclass
class _Item:
    """In-memory view of a queue or catalog markdown file."""

    path: Path
    is_catalog: bool
    fm: dict
    body: str
    original_text: str
    # set by passes that legitimately mutate a catalog file (allowlisted
    # fields only). The writer reverts in-memory mutations on catalog items
    # that DON'T carry this flag.
    catalog_mutation_allowed: bool = False
    # set during identity / URL passes; suppresses any further mutations and
    # triggers an `unlink()` at write time
    deleted: bool = False

    # --- convenience accessors -------------------------------------------------

    @property
    def slug(self) -> str:
        return str(self.fm.get("name") or self.path.stem)

    @property
    def kind(self) -> str:
        return str(self.fm.get("kind") or "")

    @property
    def url(self) -> str:
        src = self.fm.get("source") or {}
        if isinstance(src, dict):
            u = src.get("url")
            return str(u) if isinstance(u, str) else ""
        return ""

    @property
    def fingerprint(self) -> str:
        fp = self.fm.get("fingerprint")
        return fp if isinstance(fp, str) and fp else ""

    @property
    def title(self) -> str:
        return str(self.fm.get("title") or "")

    @property
    def authors(self) -> list[str]:
        src = self.fm.get("source") or {}
        if isinstance(src, dict):
            a = src.get("authors")
            if isinstance(a, list):
                return [s for s in a if isinstance(s, str)]
        return []

    @property
    def discovered_on(self) -> str:
        d = self.fm.get("discovered") or {}
        if isinstance(d, dict):
            on = d.get("on")
            return str(on) if on else ""
        return ""

    @property
    def status(self) -> str:
        return str(self.fm.get("status") or "")

    @property
    def parent(self) -> str:
        relations = self.fm.get("relations") or {}
        if isinstance(relations, dict):
            return str(relations.get("parent") or "")
        return ""


# ---------------------------------------------------------------------------
# Public entry point
# ---------------------------------------------------------------------------


def run_passes(
    queue_dir: Path,
    catalog_dir: Path,
    state_dir: Path,
    *,
    dry_run: bool = False,
    today: date | None = None,
    only_pass: str | None = None,
) -> DedupReport:
    """Run the dedup engine.

    Args:
      queue_dir, catalog_dir, state_dir: filesystem roots.
      dry_run: collect intended writes but apply none.
      today: override the date used by pass 4 (tests). Defaults to today.
      only_pass: ∈ {None, "identity", "url", "proposals", "archive"}.
    """
    today = today or date.today()
    report = DedupReport()

    items = _load_items(queue_dir, catalog_dir, report)
    ledger = _load_ledger(state_dir)
    liveness = _load_liveness(state_dir)

    if only_pass in (None, "identity"):
        report.pass1_identity_collapse = _collapse_pass(items, today, _identity_keys, ledger)
    if only_pass in (None, "url"):
        report.pass2_url_canonicalize = _collapse_pass(items, today, _canonical_keys, ledger)
    if only_pass in (None, "proposals"):
        proposed, carried = _pass3_proposals(items, today, ledger)
        report.pass3_merge_proposals = proposed
        report.rejected_proposals_carried = carried
    if only_pass in (None, "archive"):
        report.pass4_auto_archived = _pass4_archive(items, today, liveness)

    if not dry_run:
        _apply_writes(items, report)
        _save_ledger(state_dir, ledger)

    return report


# ---------------------------------------------------------------------------
# Loading
# ---------------------------------------------------------------------------


def _load_items(queue_dir: Path, catalog_dir: Path, report: DedupReport) -> list[_Item]:
    items: list[_Item] = []
    for p in sorted(queue_dir.glob("*.md")) if queue_dir.exists() else []:
        if p.name.startswith("_") or p.name == "README.md":
            continue
        loaded = _try_load(p, is_catalog=False, report=report)
        if loaded is not None:
            items.append(loaded)
    for p in sorted(catalog_dir.glob("*.md")) if catalog_dir.exists() else []:
        if p.name.startswith("_") or p.name == "README.md":
            continue
        loaded = _try_load(p, is_catalog=True, report=report)
        if loaded is not None:
            items.append(loaded)
    return items


def _try_load(path: Path, *, is_catalog: bool, report: DedupReport) -> _Item | None:
    try:
        text = path.read_text(encoding="utf-8")
    except OSError as e:
        report.errors.append(f"read-failed: {path.name}: {e}")
        return None
    fm = parse_frontmatter(text)
    if not fm:
        report.errors.append(f"no-frontmatter: {path.name}")
        return None
    body = _split_body(text)
    return _Item(
        path=path,
        is_catalog=is_catalog,
        fm=fm,
        body=body,
        original_text=text,
    )


def _split_body(text: str) -> str:
    """Return everything after the closing `---\\n` of the frontmatter block."""
    if not text.startswith("---"):
        return text
    parts = text.split("---", 2)
    if len(parts) < 3:
        return ""
    return parts[2].lstrip("\n")


def _load_ledger(state_dir: Path) -> dict:
    path = state_dir / "merge-decisions.json"
    if not path.exists():
        return {"rejected_proposals": [], "applied_collapses": []}
    try:
        data = json.loads(path.read_text())
    except (OSError, json.JSONDecodeError):
        return {"rejected_proposals": [], "applied_collapses": []}
    data.setdefault("rejected_proposals", [])
    data.setdefault("applied_collapses", [])
    return data


def _load_liveness(state_dir: Path) -> dict:
    path = state_dir / "url-liveness.json"
    if not path.exists():
        return {"checks": {}}
    try:
        data = json.loads(path.read_text())
    except (OSError, json.JSONDecodeError):
        return {"checks": {}}
    data.setdefault("checks", {})
    return data


# ---------------------------------------------------------------------------
# Pass 1 / 2 — identity & canonical-URL collapse
# ---------------------------------------------------------------------------


def _identity_keys(item: _Item) -> list[str]:
    keys: list[str] = []
    fp = fingerprint_key(item.fingerprint)
    if fp:
        keys.append(f"fp:{fp}")
    u = url_key(item.url)
    if u:
        keys.append(f"u:{u}")
    return keys


def _canonical_keys(item: _Item) -> list[str]:
    u = canonical_url_key(item.url)
    return [f"cu:{u}"] if u else []


def _collapse_pass(items: list[_Item], today: date, get_keys, ledger: dict) -> int:
    """Generic union-find collapse over an identity-key extractor.

    Survivor selection:
      - Prefer existing catalog member whose `status != archived`.
      - Else prefer queue member with `kind == "repo"` (cross-kind dedup
        recommendation: collapse to the repo form).
      - Else earliest `discovered_on`.
      - Ties broken by slug for determinism.
    """
    active = [(i, it) for i, it in enumerate(items) if not it.deleted]

    # Index: key → list of indices into `items`.
    key_to_indices: dict[str, list[int]] = {}
    for i, item in active:
        for key in get_keys(item):
            key_to_indices.setdefault(key, []).append(i)

    parent_arr = list(range(len(items)))

    def find(x: int) -> int:
        while parent_arr[x] != x:
            parent_arr[x] = parent_arr[parent_arr[x]]
            x = parent_arr[x]
        return x

    def union(a: int, b: int) -> None:
        ra, rb = find(a), find(b)
        if ra != rb:
            parent_arr[rb] = ra

    for idxs in key_to_indices.values():
        if len(idxs) < 2:
            continue
        first = idxs[0]
        for j in idxs[1:]:
            union(first, j)

    groups: dict[int, list[int]] = {}
    for i, _ in active:
        groups.setdefault(find(i), []).append(i)

    collapses = 0
    for member_idxs in groups.values():
        if len(member_idxs) < 2:
            continue
        members = [items[i] for i in member_idxs]
        # Parent-child URL aliasing: a repo's URL (`https://github.com/o/r`)
        # canonicalizes to the same value as any of its extracted children's
        # blob URLs. Those are NOT duplicates — the child is a derived asset
        # — so skip the whole group when a parent-child pair is present.
        if _group_has_parent_child(members):
            continue
        survivor = _choose_survivor(members)
        if survivor is None:
            continue
        # We never delete a catalog asset. Losers are queue items only.
        losers = [m for m in members if m is not survivor and not m.is_catalog]
        if not losers:
            continue
        _record_collapse(survivor, losers, today, ledger)
        for m in losers:
            m.deleted = True
        collapses += 1

    return collapses


def _group_has_parent_child(members: list[_Item]) -> bool:
    """True iff one member's `relations.parent` equals another member's slug."""
    slugs = {m.slug for m in members}
    return any(m.parent and m.parent in slugs for m in members)


def _choose_survivor(members: list[_Item]) -> _Item | None:
    """Pick the survivor of an identity group.

    Order of preference:
      1. Catalog member with status != archived (earliest by slug).
      2. Queue member with kind == "repo" (cross-kind: repo wins over article).
      3. Queue member with earliest discovered_on; tie-break by slug.
    """
    live_catalog = [m for m in members if m.is_catalog and m.status != "archived"]
    if live_catalog:
        return min(live_catalog, key=lambda m: m.slug)
    queue_members = [m for m in members if not m.is_catalog]
    repo_queue = [m for m in queue_members if m.kind == "repo"]
    if repo_queue:
        return min(repo_queue, key=lambda m: (m.discovered_on or "9999-12-31", m.slug))
    if queue_members:
        return min(
            queue_members,
            key=lambda m: (m.discovered_on or "9999-12-31", m.slug),
        )
    return None


def _record_collapse(
    survivor: _Item, losers: list[_Item], today: date, ledger: dict
) -> None:
    """Record an identity-collapse decision.

    For a catalog survivor we touch only `updated_at` (allowlisted field) and
    log the collapse in the ledger; the catalog body stays exactly as the
    reviewer wrote it.

    For a queue survivor we additionally append a `## Collapsed (auto)`
    section to the body so the reviewer can see what was merged when they
    open the file.
    """
    ledger.setdefault("applied_collapses", []).append(
        {
            "collapsed_at": today.isoformat(),
            "survivor": survivor.slug,
            "survivor_path": survivor.path.name,
            "discarded": sorted(m.path.name for m in losers),
        }
    )

    if survivor.is_catalog:
        survivor.fm["updated_at"] = today.isoformat()
        survivor.catalog_mutation_allowed = True
        return

    existing_block = _extract_marker_block(survivor.body, COLLAPSE_START, COLLAPSE_END)
    existing_names = (
        {m.group(1) for m in re.finditer(r"^- `([^`]+)`", existing_block, re.MULTILINE)}
        if existing_block is not None
        else set()
    )
    new_entries = [
        f"- `{m.path.name}` ({m.slug})"
        for m in losers
        if m.path.name not in existing_names
    ]
    if not new_entries:
        return
    if existing_block is not None:
        merged = existing_block.rstrip() + "\n" + "\n".join(new_entries) + "\n"
    else:
        merged = (
            f"{COLLAPSE_HEADER}\n\n"
            f"Identity-collapsed on {today.isoformat()}:\n\n"
            + "\n".join(new_entries)
            + "\n"
        )
    survivor.body = _replace_marker_block(
        survivor.body, COLLAPSE_START, COLLAPSE_END, merged
    )


# ---------------------------------------------------------------------------
# Pass 3 — soft-overlap merge proposals
# ---------------------------------------------------------------------------


def _pass3_proposals(items: list[_Item], today: date, ledger: dict) -> tuple[int, int]:
    """Bucket by (kind, primary_author); within each bucket pair items by
    title-token Jaccard ≥ JACCARD_THRESHOLD. Each resulting group of ≥2 gets
    a `mergeset_id` annotation + a proposal body section.

    Rejection contract: if a member's body has the rejected-header marker,
    the engine records the rejection in the ledger and never re-proposes.
    """
    active = [it for it in items if not it.deleted]
    rejected_ids = {p["mergeset_id"] for p in ledger.get("rejected_proposals", [])}

    buckets: dict[tuple[str, str], list[_Item]] = {}
    for it in active:
        if not it.kind:
            continue
        key = (it.kind, primary_author(it.authors))
        buckets.setdefault(key, []).append(it)

    tokens = {id(it): title_tokens(it.title) for it in active}
    proposals = 0
    carried = 0
    proposed_slugs: set[str] = set()

    for bucket_items in buckets.values():
        if len(bucket_items) < 2:
            continue
        n = len(bucket_items)
        parent_arr = list(range(n))

        for i in range(n):
            for j in range(i + 1, n):
                a, b = bucket_items[i], bucket_items[j]
                if _is_sibling_child_pair(a, b):
                    # Cross-repo children with the same `child-name`: NOT a
                    # merge by default (locked decision). Skip the pair.
                    continue
                threshold = (
                    INTRA_PARENT_JACCARD
                    if a.parent and b.parent and a.parent == b.parent
                    else JACCARD_THRESHOLD
                )
                if jaccard(tokens[id(a)], tokens[id(b)]) >= threshold:
                    _uf_union(parent_arr, i, j)

        groups: dict[int, list[int]] = {}
        for i in range(n):
            groups.setdefault(_uf_find(parent_arr, i), []).append(i)

        for group_indices in groups.values():
            if len(group_indices) < 2:
                continue
            group_items = [bucket_items[i] for i in group_indices]
            slugs = sorted(g.slug for g in group_items)
            mergeset_id = f"ms-{slug_set_hash(slugs)}"

            # Honor existing rejection.
            if mergeset_id in rejected_ids:
                carried += 1
                _strip_proposal_block_if_present(group_items, mergeset_id)
                continue
            if any(_proposal_is_rejected(g.body) for g in group_items):
                ledger.setdefault("rejected_proposals", []).append(
                    {
                        "mergeset_id": mergeset_id,
                        "members": slugs,
                        "rejected_at": today.isoformat(),
                        "reason": "human-override",
                    }
                )
                rejected_ids.add(mergeset_id)
                carried += 1
                continue

            proposals += 1
            for slug in slugs:
                proposed_slugs.add(slug)
            for it in group_items:
                _apply_proposal(it, mergeset_id, group_items, tokens)

    # Strip stale mergeset annotations from items no longer in any group.
    for it in active:
        if it.fm.get("mergeset_id") and it.slug not in proposed_slugs:
            # Don't strip if the proposal is recorded as rejected by id.
            existing = it.fm.get("mergeset_id")
            if existing not in rejected_ids:
                it.fm.pop("mergeset_id", None)
                it.body = _replace_marker_block(it.body, PROPOSAL_START, PROPOSAL_END, "")

    return proposals, carried


def _uf_find(parent_arr: list[int], x: int) -> int:
    while parent_arr[x] != x:
        parent_arr[x] = parent_arr[parent_arr[x]]
        x = parent_arr[x]
    return x


def _uf_union(parent_arr: list[int], a: int, b: int) -> None:
    ra, rb = _uf_find(parent_arr, a), _uf_find(parent_arr, b)
    if ra != rb:
        parent_arr[rb] = ra


def _is_sibling_child_pair(a: _Item, b: _Item) -> bool:
    """True when both items are repo children with different parents and the
    same child-name (i.e., `<repo-a>--<child>` vs `<repo-b>--<child>`)."""
    if not (a.parent and b.parent and a.parent != b.parent):
        return False
    a_name = a.slug.split("--", 1)[-1] if "--" in a.slug else a.slug
    b_name = b.slug.split("--", 1)[-1] if "--" in b.slug else b.slug
    return a_name == b_name


def _apply_proposal(
    item: _Item, mergeset_id: str, group_items: list[_Item], tokens: dict
) -> None:
    item.fm["mergeset_id"] = mergeset_id

    others = sorted(
        (g for g in group_items if g is not item), key=lambda g: g.slug
    )
    overlap_lines = []
    for o in others:
        score = jaccard(tokens[id(item)], tokens[id(o)])
        loc = "catalog" if o.is_catalog else "queue"
        overlap_lines.append(f"- `{o.slug}` ({loc}) — Jaccard {score:.2f}")

    catalog_targets = [o for o in group_items if o.is_catalog]
    if catalog_targets:
        recommended = min(catalog_targets, key=lambda x: x.slug)
        rec_loc = "catalog"
    else:
        recommended = min(group_items, key=lambda x: x.slug)
        rec_loc = "queue"

    section = (
        f"\n{PROPOSAL_HEADER}\n\n"
        f"This candidate appears to overlap with:\n\n"
        + "\n".join(overlap_lines)
        + "\n\n"
        + f"**Recommended action:** merge into `{recommended.slug}` ({rec_loc}).\n\n"
        + "To reject this proposal, change the header to "
        + f"`{PROPOSAL_REJECTED_HEADER}`. The engine will record the rejection "
        + "in `scout/state/merge-decisions.json` and not re-propose this "
        + f"mergeset (`{mergeset_id}`).\n"
    )
    item.body = _replace_marker_block(item.body, PROPOSAL_START, PROPOSAL_END, section)


def _proposal_is_rejected(body: str) -> bool:
    """True iff the reviewer flipped the proposal block's header to the
    rejected form. Checks the first header *inside* the marker block; the
    string also appears in the instructions text, so a plain substring check
    would false-positive on every auto-generated proposal."""
    block = _extract_marker_block(body, PROPOSAL_START, PROPOSAL_END)
    if block is None:
        return False
    for line in block.splitlines():
        stripped = line.strip()
        if not stripped:
            continue
        return stripped == PROPOSAL_REJECTED_HEADER
    return False


def _strip_proposal_block_if_present(group_items: list[_Item], mergeset_id: str) -> None:
    """Carry-over case: a mergeset was already rejected in the ledger. Keep
    the human's `(rejected)` header (so they remember why), but ensure the
    mergeset_id annotation is consistent."""
    for it in group_items:
        if it.fm.get("mergeset_id") != mergeset_id:
            it.fm["mergeset_id"] = mergeset_id


# ---------------------------------------------------------------------------
# Pass 4 — objective auto-archive
# ---------------------------------------------------------------------------


def _pass4_archive(items: list[_Item], today: date, liveness: dict) -> int:
    archived = 0
    for it in items:
        if not it.is_catalog or it.deleted:
            continue
        if it.fm.get("status") == "archived":
            continue
        reason: str | None = None
        if should_archive_for_404(it.url, liveness, today=today):
            reason = "source-url-404"
        elif should_archive_for_supersedes(it.fm, today=today):
            reason = "superseded"
        if reason is None:
            continue
        it.fm["status"] = "archived"
        it.fm["archived_reason"] = reason
        it.fm["archived_at"] = today.isoformat()
        it.fm["updated_at"] = today.isoformat()
        it.catalog_mutation_allowed = True
        archived += 1
    return archived


# ---------------------------------------------------------------------------
# Body-marker helpers
# ---------------------------------------------------------------------------


def _extract_marker_block(body: str, start: str, end: str) -> str | None:
    if start not in body or end not in body:
        return None
    s = body.index(start) + len(start)
    e = body.index(end)
    if e < s:
        return None
    return body[s:e].strip("\n")


def _replace_marker_block(body: str, start: str, end: str, new_inner: str) -> str:
    """Replace a marker-delimited block (or append a fresh one).

    Passing `new_inner=""` removes the block entirely.
    """
    if start in body and end in body:
        before = body.split(start, 1)[0].rstrip()
        after = body.split(end, 1)[1].lstrip("\n")
        if not new_inner.strip():
            joiner = "\n\n" if before and after else ""
            return (before + joiner + after).rstrip() + "\n"
        block = f"{start}\n{new_inner.strip()}\n{end}"
        before_part = (before + "\n\n") if before else ""
        after_part = ("\n\n" + after) if after else "\n"
        return before_part + block + after_part
    if not new_inner.strip():
        return body
    base = body.rstrip()
    block = f"{start}\n{new_inner.strip()}\n{end}"
    sep = "\n\n" if base else ""
    return base + sep + block + "\n"


# ---------------------------------------------------------------------------
# Writes
# ---------------------------------------------------------------------------


def _apply_writes(items: list[_Item], report: DedupReport) -> None:
    """Persist mutations to disk. Catalog assets get an allowlist guard."""
    for it in items:
        if it.deleted:
            with contextlib.suppress(FileNotFoundError):
                it.path.unlink()
            continue

        if it.is_catalog and not it.catalog_mutation_allowed:
            # No allowlisted change happened; do NOT touch the file even if
            # a pass incidentally annotated mergeset_id or appended a section.
            # Strip those in-memory mutations and skip the write.
            it.fm = parse_frontmatter(it.original_text)
            it.body = _split_body(it.original_text)
            continue
        if it.is_catalog:
            # Catalog allowlist: every field in `fm` must be either pre-existing
            # or in CATALOG_ALLOWED_FIELDS. Revert any non-allowlisted *new*
            # field that crept in (e.g. mergeset_id).
            original_fm = parse_frontmatter(it.original_text)
            for k in list(it.fm.keys()):
                if k in original_fm:
                    if k not in CATALOG_ALLOWED_FIELDS and it.fm[k] != original_fm[k]:
                        it.fm[k] = original_fm[k]
                else:
                    if k not in CATALOG_ALLOWED_FIELDS:
                        it.fm.pop(k, None)
            # Catalog bodies are reviewer-authored — never rewrite the body.
            it.body = _split_body(it.original_text)

        new_text = _render(it)
        if new_text != it.original_text:
            it.path.write_text(new_text)


def _render(item: _Item) -> str:
    fm_yaml = yaml.safe_dump(item.fm, sort_keys=False, default_flow_style=False)
    body = item.body
    # Ensure body has at most one trailing newline before we append it.
    body = body.rstrip("\n") + "\n"
    return f"---\n{fm_yaml}---\n\n{body}"


def _save_ledger(state_dir: Path, ledger: dict) -> None:
    state_dir.mkdir(parents=True, exist_ok=True)
    path = state_dir / "merge-decisions.json"
    # Deterministic ordering + dedup. Idempotent re-runs must produce the
    # same file byte-for-byte.
    ledger["rejected_proposals"] = _dedup_dict_list(
        ledger.get("rejected_proposals", []), key=lambda p: p.get("mergeset_id", "")
    )
    ledger["applied_collapses"] = _dedup_dict_list(
        ledger.get("applied_collapses", []),
        key=lambda e: (e.get("survivor", ""), tuple(e.get("discarded", []))),
    )
    if path.exists():
        existing = path.read_text()
        new = json.dumps(ledger, indent=2, sort_keys=True) + "\n"
        if existing == new:
            return
        path.write_text(new)
    else:
        # Only create the ledger file when there's something to record.
        if ledger["rejected_proposals"] or ledger["applied_collapses"]:
            path.write_text(json.dumps(ledger, indent=2, sort_keys=True) + "\n")


def _dedup_dict_list(items: list[dict], *, key) -> list[dict]:
    seen: dict[Any, dict] = {}
    for it in items:
        k = key(it)
        # First occurrence wins (preserves earliest `collapsed_at`).
        seen.setdefault(k, it)
    return sorted(seen.values(), key=key)
