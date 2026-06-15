---
name: phase-3-scout-v2-security
title: "Phase 3 — scout v2: HN / Lobsters / Reddit on a security baseline"
phase: 3
status: done
created_at: 2026-06-14
updated_at: 2026-06-15
completed_at: 2026-06-14
commit_shas: [be5809a]
supersedes: []
superseded_by:
related: [phase-3-model-and-effort-recommendation, phase-4-repo-extractor]
locked_decisions:
  - "Stack: Python 3.11+, uv-managed venv, monorepo, markdown + YAML frontmatter as catalog DB."
  - "Reviewer trust model: human-only, forever. Any future agent reviewer requires a new section in security.md first."
  - "Phase 4 sandboxing: container per clone (Docker / podman). Documented here; implemented in Phase 4."
  - "sanitize_text length cap: silent truncate. No marker, no metadata."
  - "SSRF defense: literal-IP check only (no DNS resolution). Residual hostname-bypass risk documented as known future activity."
  - "Polymorphic catalog: one <slug>.md per asset, kind: in frontmatter."
  - "Scout source roster: GitHub is extraction target, not discovery surface."
  - "Phase 3 shipped as one logical commit covering retrofit + three new extractors."
notes: >
  Originated outside the repo (planning artefact named
  ~/.claude/plans/serene-prancing-raven.md). Imported on 2026-06-15 to
  satisfy the planning-lineage rule in CLAUDE.md. Body unchanged from
  the original.
---

# Plan: complete Phase 3 (HN / Lobsters / Reddit extractors) on a Phase 3.0 security baseline

## Context

The autoclaude repo (working dir `/code/autoclaude`) has shipped Phases 0–2 + a uv migration with a unit/integration test split. Phase 3 (three new scout extractors) is partially written but uncommitted, AND a security gap was identified before extracting from repositories begins in Phase 4. The user committed to a security baseline that retrofits Phase 2 + in-progress Phase 3 code before any new extractor work continues.

The goal of this handoff plan is to let a fresh Claude Code session (or delegated subagents) finish the work end-to-end without re-deriving the context. Read the references below in order; they are deliberately concise.

## Required reading (in this order)

1. `/code/autoclaude/CLAUDE.md` — the repo's operating brief.
2. `/code/autoclaude/conventions/security.md` — written this session; defines the rules.
3. `/code/autoclaude/conventions/testing.md` — the test protocol (will be amended; see task 1).
4. `/code/autoclaude/scout/_security.py` — written this session; the toolkit every extractor must use.
5. `/code/autoclaude/scout/extractors/awesome_list.py` — committed Phase 2 reference; needs retrofit (task 2).
6. `/code/autoclaude/scout/agent/runner.py` — committed Phase 2 orchestrator; needs the new dispatch entries.

## Locked decisions (do NOT relitigate)

- **Stack:** Python 3.11+, uv-managed venv, single monorepo, markdown + YAML frontmatter as the catalog DB.
- **Reviewer trust model:** Human-only, forever (Phase 1 v1). Sanitization is belt-and-suspenders. Any future agent reviewer requires a new section in `security.md` *first*.
- **Phase 4 sandboxing:** Container per clone (Docker / podman). Document only; Phase 4 work is out of scope here.
- **Retrofit scope:** Phase 2 awesome-list + in-progress Phase 3 (HN, Lobsters). Reddit will be written fresh on the security baseline.
- **`sanitize_text` truncation:** Silent truncate at `max_length`. No marker, no metadata field for "was truncated."
- **SSRF defense:** Literal-IP check only (no DNS resolution). The residual hostname-bypass risk is noted in `security.md` as a known future activity.
- **Catalog asset model:** Polymorphic, one `<slug>.md` file per asset, distinguished by `kind:` in frontmatter. See `/code/autoclaude/catalog/_schema/asset.schema.md`.
- **Scout source roster:** GitHub is the *extraction target*, not a discovery surface. Discovery comes from awesome-lists (Phase 2, shipped), HN/Lobsters/Reddit (this plan), X/Twitter (deferred to Phase 5).
- **Commit cadence:** Phase 3 ships as **one** logical commit covering the security retrofit AND the three new extractors. See the commit-message template at the end.

## State of the working tree (uncommitted as of plan time)

Branch: `main` (no feature branch — single-author repo).

Committed:
- `42266fe` Phase 0
- `bb258d8` Phase 1
- `9ffe1f3` Phase 2
- `f6efdfa` uv migration + test scaffold

Uncommitted (run `git status --short` to confirm):

- `scout/_util.py` — modified: added `classify_url`, `is_github_repo_url`, `matches_any`; expanded `_GITHUB_NOT_USEFUL` regex.
- `scout/agent/types.py` — modified: added `MatchSpec`, `_FilteredSource`, `HackerNewsSource`, `LobstersSource`, `RedditSource`.
- `scout/extractors/awesome_list.py` — modified: refactored to use shared helpers from `_util` (`classify_url`); **NOT YET retrofitted for security**.
- `scout/extractors/hackernews.py` — **new**, uses `client.get(...).json()`; **NOT YET retrofitted for security**.
- `scout/extractors/lobsters.py` — **new**, uses **stdlib `xml.etree.ElementTree`** and `client.get(...).text`; **NOT YET retrofitted**.
- `pyproject.toml` — modified: `defusedxml>=0.7` added to `dependencies`.
- `uv.lock` — refreshed (`defusedxml==0.7.1` now in the lock).
- `conventions/security.md` — **new**, written this session.
- `conventions/README.md` — modified: linked `security.md`.
- `scout/_security.py` — **new**, written this session: `sanitize_text`, `safe_external_url`, `safe_get_bytes`, `UnsafeURLError`, `ResponseTooLargeError`, `SecurityError`.

Source YAMLs at `scout/sources/hackernews.yaml`, `lobsters.yaml`, `reddit.yaml` are currently `enabled: false`. They get flipped to `true` at task 12.

## Remaining tasks (in order)

The tasks below assume a fresh session. Each task lists what to do, what files to touch, and what "done" looks like. The tasks are sequenced so the suite stays green after every step — do not skip ahead.

### 1. Append security-test rule to `conventions/testing.md`

Add a new top-level section "Security tests for extractors" requiring every new extractor's unit test to include at least one adversarial case demonstrating the security helpers fire. Three example assertions to include (one of these must appear in each extractor's test file):

- Oversized response → `ResponseTooLargeError` raised (or caught and recorded in `state.stats`).
- Title with bidirectional override → sanitized in the yielded Candidate.
- Redirect to a private IP → `UnsafeURLError` raised.

Treat this as gate, not nice-to-have.

### 2. Write `tests/unit/test_security.py` (adversarial coverage of `scout/_security.py`)

Cover:

- `sanitize_text`:
  - strips null bytes
  - strips U+202E (RIGHT-TO-LEFT OVERRIDE) and other bidi range
  - strips U+200B (ZWSP) and other zero-width
  - strips surrogate halves and private-use chars
  - preserves `\t \n \r`
  - collapses runs of spaces+tabs to a single space
  - collapses 3+ newlines to `\n\n`
  - NFC-normalizes (`café` → `café`)
  - handles `None` → `""`
  - handles non-string → str-coerced then sanitized
  - silent truncate at `max_length` (no marker)

- `safe_external_url`:
  - allows `https://example.com`, `https://github.com/foo/bar`, `http://example.com:8080/path`
  - rejects `javascript:`, `file://`, `ftp://`, `data:`
  - rejects `http://localhost/`, `http://127.0.0.1/`, `http://10.0.0.5/`, `http://192.168.1.1/`, `http://172.16.0.5/`, `http://169.254.169.254/latest/` (AWS metadata)
  - rejects `http://[::1]/`, `http://[fe80::1]/`
  - rejects `""`, `"not a url"`, `"https://"`

- `safe_get_bytes`:
  - rejects unsafe URL pre-request → `UnsafeURLError`
  - rejects redirect to a private IP → `UnsafeURLError` (use `httpx.MockTransport` returning a 301 to `http://127.0.0.1/`)
  - rejects content-length > max → `ResponseTooLargeError`
  - rejects streamed body exceeding max → `ResponseTooLargeError`
  - returns bytes on normal response

Use `httpx.MockTransport` and the `make_mock_httpx_client` factory in `tests/conftest.py` where applicable.

### 3. Retrofit `scout/extractors/awesome_list.py` with security helpers

In the per-list loop:

```python
# Before:
resp = self._client.get(lst.url)
resp.raise_for_status()
content = resp.text

# After:
from .._security import safe_get_bytes, SecurityError, sanitize_text
try:
    content = safe_get_bytes(self._client, lst.url).decode("utf-8", errors="replace")
except (SecurityError, httpx.HTTPError) as e:
    state.stats.setdefault("list_errors", []).append(
        {"list": lst.name, "url": lst.url, "error": str(e), "at": today}
    )
    continue
```

Before `yield Candidate(...)`, sanitize:

```python
title = sanitize_text(match.group(1), max_length=300)
```

Existing `tests/unit/test_awesome_list_extractor.py` must remain green — the mocked transport in those tests does NOT hit `safe_external_url` blocks because the mock URL `https://example.invalid/...` is treated as a public hostname. Add one new test case there feeding a bidi-laden title and asserting the yielded candidate's title is sanitized.

### 4. Retrofit `scout/extractors/hackernews.py`

Replace `resp.raise_for_status()` + `resp.json()` pattern with:

```python
import json
from .._security import safe_get_bytes, SecurityError, sanitize_text

try:
    body = safe_get_bytes(self._client, source.endpoint, params=params)
    hits = json.loads(body).get("hits", [])
except (SecurityError, httpx.HTTPError, json.JSONDecodeError) as e:
    state.stats.setdefault("term_errors", []).append(
        {"term": term, "error": str(e), "at": today}
    )
    continue
```

In the per-hit loop, sanitize:

```python
title = sanitize_text(hit.get("title") or "untitled", max_length=300)
author = sanitize_text(hit.get("author") or "", max_length=100)
```

Note that `params` must be a `dict[str, str]` for `safe_get_bytes` (the helper accepts it via `params=`).

### 5. Retrofit `scout/extractors/lobsters.py`: defusedxml + security

Replace at top of file:

```python
# Before:
import xml.etree.ElementTree as ET

# After:
from defusedxml import ElementTree as ET
```

In the per-feed loop, replace:

```python
# Before:
resp = self._client.get(feed_url)
resp.raise_for_status()
root = ET.fromstring(resp.text)

# After:
try:
    body = safe_get_bytes(self._client, feed_url)
    root = ET.fromstring(body)   # defusedxml accepts bytes
except (SecurityError, httpx.HTTPError, ET.ParseError) as e:
    state.stats.setdefault("feed_errors", []).append(
        {"feed": feed_url, "error": str(e), "at": today}
    )
    continue
```

Sanitize before yielding Candidate:

```python
title = sanitize_text(title_raw, max_length=300)
```

### 6. Write `scout/extractors/reddit.py` (fresh, with security baked in)

Class `RedditExtractor`, `type = "reddit"`. Constructor mirrors others (accepts injectable `httpx.Client`, default UA `"autoclaude-scout/0.1.0"`).

For each subreddit in `source.subreddits`:

```python
url = f"https://www.reddit.com/r/{sub}/new.json?limit=100"
try:
    body = safe_get_bytes(self._client, url)
    children = json.loads(body)["data"]["children"]
except (SecurityError, httpx.HTTPError, json.JSONDecodeError, KeyError) as e:
    state.stats.setdefault("sub_errors", []).append(
        {"sub": sub, "error": str(e), "at": today}
    )
    continue
```

Per child `data`:

- Skip if `is_self == True`.
- Skip if URL's host is `reddit.com`, `www.reddit.com`, `i.redd.it`, `v.redd.it`, `redd.it`.
- Skip if `created_utc <= cursor.get("per_sub", {}).get(sub, 0)`.
- Skip if `matches_any(title, source.match.any_of)` is False (use the helper from `_util.py`).
- Classify URL via `classify_url(url)`; skip if None.
- Sanitize title (max 300) and author (max 100).
- Dedup against `state.seen_urls`.
- Yield Candidate with `discovered_via=f"reddit-{sub.lower()}"`, `raw_url=f"https://www.reddit.com{permalink}"`, `score=score`.

Track per-sub cursor in `state.cursor["per_sub"][sub] = max_seen_created_utc` (write at end of each sub).

### 7. Register HN / Lobsters / Reddit in `scout/agent/runner.py`

Two dict updates only:

```python
# imports
from ..extractors.hackernews import HackerNewsExtractor
from ..extractors.lobsters import LobstersExtractor
from ..extractors.reddit import RedditExtractor
from .types import (
    AwesomeListSource,
    HackerNewsSource,
    LobstersSource,
    RedditSource,
    Candidate,
    SourceState,
)

EXTRACTOR_REGISTRY: dict[str, object] = {
    "awesome-list": AwesomeListExtractor(),
    "hackernews": HackerNewsExtractor(),
    "lobsters": LobstersExtractor(),
    "reddit": RedditExtractor(),
}

SOURCE_MODELS: dict[str, type] = {
    "awesome-list": AwesomeListSource,
    "hackernews": HackerNewsSource,
    "lobsters": LobstersSource,
    "reddit": RedditSource,
}
```

### 8. Add fixture files in `tests/fixtures/`

Three realistic but small fixture files. Each one is loaded by the extractor's unit test via the pattern in `tests/fixtures/README.md`.

- **`hn-search-results.json`** — Algolia response with ≥4 hits:
  1. A Show-HN with `url: https://github.com/alice/foo`, `points: 42`, `objectID: "39000001"` → expected to yield.
  2. An Ask-HN with `url: null`, `points: 5` → expected to skip (no URL).
  3. A blog article with `url: https://example.com/post`, `points: 30` → expected to yield as `article`.
  4. A low-score hit with `points: 2` → expected to skip when `min_points: 10`.
  Plus a hit with a bidi-override in `title` for the security assertion.

- **`lobsters-rss.xml`** — RSS 2.0 with ≥3 `<item>`s:
  1. Match on "claude" → github link → repo yield.
  2. No keyword match → skip.
  3. Match on "anthropic" → article yield (not github).
  Plus an item whose `<title>` contains a zero-width-joiner that must be stripped.

- **`reddit-new.json`** — Reddit JSON with `data.children` containing ≥4 entries:
  1. `is_self: false`, github URL, title contains "claude" → yield.
  2. `is_self: true` → skip.
  3. `is_self: false`, anthropic.com URL, title contains "claude" → yield as article.
  4. `is_self: false`, `i.redd.it/foo.jpg` URL → skip.
  Plus one entry with a U+200B in the title for the security assertion.

### 9. Write `tests/unit/test_hackernews_extractor.py`

Pattern matches `tests/unit/test_awesome_list_extractor.py`. Use `httpx.MockTransport` that returns the fixture JSON for any GET to the Algolia endpoint. Cover:

- happy-path emits expected number of Candidates with correct `kind` (`repo` vs `article`)
- `min_points` filter rejects low-score
- empty `url` (Ask HN) is skipped
- `objectID` dedup within a run (same hit returned for two query terms only emits once)
- cursor advances: `state.cursor["last_seen_created_at_i"]` updates to the max seen
- second run with non-zero cursor adds `numericFilters=created_at_i>...` to params (verify via inspecting the captured request)
- **security:** bidi-override in the fixture's title comes out sanitized in the yielded Candidate

### 10. Write `tests/unit/test_lobsters_extractor.py`

Same pattern with the XML fixture. Cover:

- happy-path emits only items matching `match.any_of`
- repo/article classification via URL
- cursor advances (`state.cursor["last_seen_pub_ts"]` updates)
- second run skips items with `pubDate <= cursor`
- malformed XML → caught and recorded in `state.stats`
- **security:** zero-width-joiner in a title comes out sanitized

### 11. Write `tests/unit/test_reddit_extractor.py`

Cover:

- happy-path emits Candidates only for non-`is_self`, non-redd.it URLs that match keywords
- per-sub cursor: `state.cursor["per_sub"]["claudecode"]` advances per sub
- `discovered_via` is `f"reddit-{sub.lower()}"`
- **security:** U+200B in a title comes out sanitized; a fake 301 redirect from `https://www.reddit.com/...` to `http://10.0.0.1/` raises `UnsafeURLError` (handled by the extractor's try/except and recorded in `state.stats`)

### 12. Re-enable `scout/sources/{hackernews,lobsters,reddit}.yaml`

Flip `enabled: false` → `enabled: true` in all three. Remove the "# flip on in Phase 3 …" comment.

### 13. Run the full quality gate

```sh
uv run ruff check scout/ tests/         # must be clean
uv run pytest -q                        # must be all green
uv run pytest tests/integration -q      # 2 pass (existing)
```

### 14. Smoke test each new source live

One at a time, inspect:

```sh
rm -rf scout/state/hackernews.json scout/state/lobsters.json scout/state/reddit.json   # ensure fresh cursors
uv run scout run -s hackernews -v
ls scout/queue/ | wc -l
cat scout/state/hackernews.json | head -30
uv run scout run -s hackernews -v       # second run should queue 0 (cursor advanced)

uv run scout run -s lobsters -v
uv run scout run -s reddit -v
```

If any source 4xx/5xx/rate-limits: capture the error in the thread log under `/command-center/threads/`, do not block the commit on a flaky external source; mention the issue in the commit body.

The Reddit endpoint is occasionally fussy about User-Agent. If 429s persist, switch the request to `https://old.reddit.com/r/<sub>/new.json` (functionally identical, more lenient).

### 15. Update docs

- `scout/extractors/README.md` — flip the HN/Lobsters/Reddit status rows from "Phase 3" to "**Phase 3 — `<module>.py`**"; add a short note that all extractors use `_security.safe_get_bytes` for HTTP and `_security.sanitize_text` on free-form fields.
- `scout/README.md` — change the line about "Phase 2 ships in awesome_list.py; the rest land per the roadmap" to reflect Phase 3 completion.
- `CLAUDE.md` — Phase plan: mark Phase 3 done. Bump Phase 4's framing to "GitHub repo extractor in a per-clone container, per `/conventions/security.md`".
- `README.md` — update the Status line to "Phase 3 shipped — three social/list sources feeding the catalog queue".

### 16. Commit Phase 3 as one logical change

Suggested commit message:

```
Phase 3: HN/Lobsters/Reddit extractors on a security baseline

Security baseline (Phase 3.0):
- conventions/security.md captures the threat model: prompt injection via
  scraped content, code execution via cloned repos (Phase 4), SSRF + parser
  attacks. Locks in the rules every extractor must follow.
- scout/_security.py with sanitize_text (NFC + strip dangerous Unicode +
  whitespace collapse + silent length-cap), safe_external_url (literal-IP
  check; rejects loopback/private/link-local), safe_get_bytes (URL-validated,
  size-bounded streaming GET that re-checks the URL after redirects).
- defusedxml dep added; lobsters parser switched off stdlib xml.etree.
- Phase 2 awesome-list extractor retrofitted to use the helpers; existing
  test gains a bidi-sanitization assertion.

Three new extractors (Phase 3):
- HackerNews (Algolia search_by_date): one query per match.any_of term,
  dedup by objectID, filter by min_points, classify URL as github-repo vs
  article. Cursor: max created_at_i seen.
- Lobsters (per-tag RSS via defusedxml): title-keyword filter, RFC-2822
  pubDate cursor.
- Reddit (/r/<sub>/new.json per sub): skips is_self + redd.it domains,
  per-sub cursor in state.cursor["per_sub"], discovered_via=reddit-<sub>.

All three registered in scout/agent/runner.py EXTRACTOR_REGISTRY +
SOURCE_MODELS. Source YAMLs flipped to enabled: true.

Tests: every new extractor unit-tests at least one adversarial input per the
new convention in conventions/testing.md. Suite still <1s locally.

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
```

## Verification

Before declaring done:

```sh
git status --short          # only intentional files staged; .venv, queue/, state/, threads/ all ignored
uv run ruff check scout/ tests/      # clean
uv run pytest -q                     # all green
uv run pytest tests/integration -q   # 2 pass (existing run_once tests)
uv run scout run -v                  # exit 0, errors=0, queued > 0 OR explained
git log --oneline | head -5          # confirm the new commit is on top
```

Inspect at least one queued candidate from each new source by opening a `/scout/queue/*.md` file written during the smoke test and verifying:

- Frontmatter has the expected `kind`, `source.type`, `source.url`, `discovered.via`.
- `scout.raw_url` points back to the HN item / Lobsters discussion / Reddit permalink.
- No control characters or bidi codepoints in `title` (run `LC_ALL=C cat` and look for visible junk).

## Out of scope (do NOT do in this plan's execution)

- Phase 4 (GitHub repo extractor). Plan it separately — the security baseline laid down here is its foundation, not its implementation.
- DNS-resolution-aware SSRF defense. Documented as a future activity in `security.md`; do not add now.
- Agent-driven queue review. Trust model is human-only forever for v1; if changed, `security.md` gets a new section first.
- X / Twitter ingestion (Phase 5).
- Any catalog promotion (`/scout/queue/*.md` → `/catalog/<slug>.md`). That's a separate human-in-the-loop session.

## Critical file paths to know

- `/code/autoclaude/conventions/security.md` — security rules (committed in this plan's commit).
- `/code/autoclaude/conventions/testing.md` — test rules (will be amended).
- `/code/autoclaude/scout/_security.py` — security toolkit.
- `/code/autoclaude/scout/_util.py` — shared helpers (slugify, canonical_github_url, classify_url, matches_any, is_github_repo_url, parse_frontmatter).
- `/code/autoclaude/scout/agent/types.py` — pydantic models including MatchSpec + 4 source models.
- `/code/autoclaude/scout/agent/runner.py` — orchestrator; needs the 3 new registry entries.
- `/code/autoclaude/scout/extractors/awesome_list.py` — to retrofit.
- `/code/autoclaude/scout/extractors/hackernews.py` — written, needs retrofit.
- `/code/autoclaude/scout/extractors/lobsters.py` — written, needs defusedxml + retrofit.
- `/code/autoclaude/scout/extractors/reddit.py` — to write fresh.
- `/code/autoclaude/scout/sources/{hackernews,lobsters,reddit}.yaml` — flip enabled: true.
- `/code/autoclaude/tests/conftest.py` — `sample_candidate` and `make_mock_httpx_client` factory.
- `/code/autoclaude/tests/integration/conftest.py` — `scout_world` fixture; auto-applies the `integration` marker.
- `/code/autoclaude/tests/fixtures/README.md` — convention for loading fixture data.

## Suggested execution order for delegation

For a fresh session with subagent delegation, this work breaks into three roughly parallel chunks after the security baseline is locked:

1. **Chunk A (sequential, lays foundation):** task 1 → 2 → 3. Touches `conventions/testing.md`, `tests/unit/test_security.py`, `scout/extractors/awesome_list.py`, `tests/unit/test_awesome_list_extractor.py`. Verify with `uv run pytest -q`.

2. **Chunk B (parallel-safe with Chunk C):** tasks 4 + 9 (HN extractor retrofit + its unit test + HN fixture). One subagent.

3. **Chunk C (parallel-safe with Chunk B):** tasks 5 + 10 (Lobsters extractor retrofit + its unit test + Lobsters fixture). One subagent.

4. **Chunk D (after A finishes):** tasks 6 + 11 (Reddit extractor fresh + its unit test + Reddit fixture). One subagent. Must run after Chunk A because it depends on the security helpers being imported in the now-canonical pattern.

5. **Chunk E (sequential, integrate):** task 7 (register in runner) → task 12 (flip YAMLs) → task 13 (quality gate) → task 14 (smoke test) → task 15 (docs) → task 16 (commit).

Each chunk's subagent should: (a) read the relevant section of this plan, (b) read the listed files, (c) make the changes, (d) run only its own tests + ruff, (e) report back. The orchestrating session merges, runs the full gate, and commits.
