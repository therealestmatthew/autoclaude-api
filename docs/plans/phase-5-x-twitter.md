---
name: phase-5-x-twitter
title: "Phase 5 — X / Twitter ingestion"
phase: 5
status: done
created_at: 2026-06-15
updated_at: 2026-06-15
completed_at: 2026-06-15
supersedes: []
superseded_by:
locked_decisions:
  - "Scout remains discovery-only. X is a discovery surface; extracted github.com/* URLs go through the Phase 4 repo extractor. Set in Phase 4."
  - "Reviewer trust model: human-only. Posts land in /scout/queue/, never directly in /catalog/. Set in Phase 0/3."
  - "Every X-derived free-form string (post body, author display name) passes through scout/_security.py::sanitize_text. Set in Phase 3."
  - "Phase 5 chose option (c): defer indefinitely. $100/mo for paid Basic API is unjustified at our scale; third-party mirrors (Nitter, Bluesky bridges) are too operationally fragile to depend on. HN / Reddit echo channels already surface high-signal X content. Set here, 2026-06-15."
  - "The XExtractor stub raises NotImplementedError; XSource is registered in scout/agent/types.py and runner.py SOURCE_MODELS / EXTRACTOR_REGISTRY so the registry shape stays consistent and `scout/sources/x-handles.yaml` validates. Set here."
  - "Re-opening the decision (paid access becomes viable, or a third-party aggregator stabilizes) requires a new plan that `supersedes: [phase-5-x-twitter]` rather than reopening this one. Set here."
---

# Phase 5 — X / Twitter ingestion

## Goal

Given a configured list of X handles (already declared in
`scout/sources/x-handles.yaml`, currently `enabled: false`), surface recent
posts that mention catalog-relevant terms or link to `github.com/*`, and
queue them as `kind: article` Candidates with the embedded github URL
captured for downstream extraction by Phase 4's `RepoExtractor`.

Output of the phase: the discovery surface widens to cover a channel that
currently dominates Claude-tooling discourse but isn't reachable by
HN/Lobsters/Reddit/awesome-list extractors. Closes one of the three known
blind spots in scout v2 (the other two: paywalled aggregators, Discord).

## Non-goals (out of scope for this phase)

- Replying, posting, or any write operations against X. Read-only forever.
- Following the social graph (who-follows-who, reply trees). We ingest a
  configured handle list, not a crawl.
- Sentiment analysis or "interestingness" scoring beyond the existing
  `match.any_of` keyword filter. Ranking is Phase 6's problem.
- DMs, lists, private accounts. Public timelines only.
- Real-time streaming. Polling on `poll_interval_minutes` per
  `scout/sources/x-handles.yaml` (currently 240, i.e. four hours).

## Constraints (inherited)

From `conventions/security.md`:

- **Every HTTP call goes through `safe_get_bytes`** (or, for the API path,
  a thin wrapper that re-applies the same URL allowlist + size cap + final-
  URL re-check).
- **Every free-form string** (post body, author display name, embedded
  link text) runs through `sanitize_text` with appropriate cap before
  yielding a `Candidate`. X posts can carry the same bidi / zero-width /
  private-use attacks as anything else on the public internet.
- **No bare XML.** If we ever fall back to an RSS/Atom mirror, parsing
  goes through `defusedxml`.
- **The human is the gate.** Candidates are `status: draft` in
  `/scout/queue/`; promotion to `/catalog/` is human-only.

## The auth question (decision required this phase)

X API access is paid as of 2026. `scout/sources/x-handles.yaml` already
documents the three options:

- **(a) Pay for API access.** $100/mo Basic tier gives ~10k posts/month
  read across the handle list — plenty for the configured 4 handles at a
  4-hour cadence. Cost is the issue.
- **(b) Use a third-party aggregator.** Nitter has been intermittently
  available; Bluesky bridges exist for some accounts but not all four.
  Operational fragility is the issue.
- **(c) Defer indefinitely** and rely on HN/Reddit echoes for X-originated
  signal.

The session running this plan picks one and the answer moves into
`locked_decisions:` at phase close. Default recommendation: **(c) defer**
unless the operator explicitly wants to spend the $100/mo. The HN/Reddit
echo path already catches the signal that crosses a threshold; the long
tail of X-only posts is mostly noise after `match.any_of` filtering.

If the answer is **(c)**, the deliverable shrinks to: keep
`scout/sources/x-handles.yaml` accurate, document the deferral in the
plan's `locked_decisions:`, and move on to Phase 6. The XExtractor stub
still ships (raising `NotImplementedError`) so the registry shape is
consistent.

If the answer is **(a)** or **(b)**, the deliverable is the full
extractor.

The rest of this plan assumes **(a) paid Basic-tier access** — that's the
most-code path; the (b) and (c) paths are subsets.

## Design (assuming paid API access)

### Auth

Bearer token in `~/.config/autoclaude/x-bearer.env` (or `XAI_BEARER` env
var). Never checked into the repo. `scout/agent/runner.py` reads it once
per tick and passes a configured `httpx.Client` to the extractor.

If the token is missing and the source is `enabled: true`, the extractor
records a per-source error (the same path HN/Reddit/Lobsters errors take)
and the run continues. We do *not* hard-fail the whole tick — other
sources should still progress.

### API surface

X API v2, `/users/by/username/{handle}` to resolve handle → user_id once
(cached in `scout/state/x-handles.json`), then `/users/{id}/tweets` with
`tweet.fields=created_at,entities,public_metrics`, `max_results=20`,
`since_id=<cursor>` for incremental pulls.

`entities.urls` carries expanded URLs — that's where the
`github.com/*` filter applies. `public_metrics.like_count` gives a
soft signal but we don't filter on it in v1 (volume is low enough on the
configured 4 handles that the keyword filter is the only gate that
matters).

### Cursor / state

Per `scout/state/x-handles.json`:

```json
{
  "source": "x-handles",
  "cursor": {
    "<handle>": {
      "user_id": "...",
      "since_id": "<last-seen-tweet-id>",
      "last_pulled_at": "ISO"
    }
  },
  "seen_urls": { ... },
  "stats": { ... }
}
```

`since_id` is the X-native incremental cursor; the runner never re-pulls a
post once seen. `seen_urls` is the same dedup map every extractor uses,
keyed by the **expanded** GitHub URL inside the post (not the t.co
shortlink — those rotate and break dedup).

### Candidate shape

One Candidate per post that survives the filter. `kind: article` (a post
*about* something, with the embedded URL captured), not `kind: repo` —
the github URL goes into `scout.raw_url` and Phase 4's queue-driven
extractor picks it up on the next tick. This keeps the X extractor
ignorant of repo-specific logic.

```yaml
name: <slugify(post-text first 60 chars)>
kind: article
title: <sanitize_text(post-body, max=300)>
source_type: x
source_url: https://x.com/<handle>/status/<tweet-id>
source_authors: [<handle>]
discovered_via: x-handles
discovered_on: <today>
scout:
  raw_title: <original post body>
  raw_url: <expanded github URL if present, else the x.com URL>
  excerpt: <sanitize_text(post-body, max=2000)>
```

If a post contains multiple github URLs, we emit **one Candidate per
URL** — they review independently. Posts with no github URL but matching
`match.any_of` keywords are emitted with the x.com URL as both
`source_url` and `raw_url`.

### Failure modes

| Failure                                  | Action                                                                                |
| ---------------------------------------- | ------------------------------------------------------------------------------------- |
| Bearer missing                           | Record per-source error; continue the run; source's `state.stats.errors`.             |
| 401 / 403 (bad bearer, suspended account)| Record per-source error; mark handle's cursor with `last_error_at`; continue.         |
| 429 (rate limited)                       | Record per-source error; back off until next tick. Don't burn the remaining budget.   |
| Network / DNS / connection error         | Record per-source error; continue with the other handles.                             |
| Per-tweet URL fails `safe_external_url`  | Skip that URL; continue the post (it may have other valid URLs).                      |
| Post body exceeds sanitize cap           | Truncated silently (same as every other extractor — `sanitize_text` is the contract). |

## Code surface (rough)

New files:

```
scout/
  extractors/
    x.py                     XExtractor: per-handle pull, since_id cursor, keyword + URL filter
scout/sources/
  x-handles.yaml             flip `enabled: true` if we proceed; otherwise leave disabled
```

Updated files:

```
scout/agent/types.py         + XSource pydantic model
scout/agent/runner.py        + register XExtractor + XSource in the two dispatch dicts
conventions/security.md      + note that bearer tokens live outside the repo
docs/runbooks/scout-run.md   + section on bearer setup and rotation
```

New tests:

```
tests/unit/
  test_x_extractor.py        keyword filter, since_id advancement, URL expansion,
                              sanitize_text on post bodies, adversarial input
                              (bidi in display name; t.co never appears in source_url)
tests/integration/
  test_run_once_x.py         end-to-end with mocked X API; ensure children of github
                              URLs land in queue and the runner's queue-driven path
                              picks them up on the next tick.
tests/fixtures/
  x-tweets-anthropicai.json  fixture API response (sanitized, no real bearer)
```

## Open questions to resolve during the session

1. **Pay, mirror, or defer?** See "The auth question" above. *Recommendation: defer in v1; ship the XExtractor stub.*
2. **If we proceed: handle the bearer how?** Env var read once per process, or per-tick reload to support rotation? *Recommendation: env var read once per process; rotation via process restart is fine for daily cadence.*
3. **One Candidate per github URL in a post, or one per post?** *Recommendation: one per github URL when ≥1 URL is present; otherwise one per post.*
4. **What's the right `match.any_of` set for X specifically?** The Phase 3 keyword list was tuned for HN; X is higher-personality. *Recommendation: start with the existing `claude code`, `claude-code`, `mcp`, `github.com/` and tune after one week of real data.*
5. **Do we ingest replies, or only top-level posts?** Replies are noisy but sometimes carry the github URL the parent forgot. *Recommendation: top-level only in v1; revisit if dedup proves the parent rarely echoes the child.*

Each open question gets answered in the commit; the answer moves into `locked_decisions:` on this plan's frontmatter at phase close.

## Task breakdown (suggested execution order)

| #  | Task                                                                                       | Parallelizable with |
| -- | ------------------------------------------------------------------------------------------ | ------------------- |
| 1  | Resolve the auth question. If deferring: write the XExtractor stub + update docs, skip to task 10. | (decision first)    |
| 2  | Add `XSource` to `scout/agent/types.py`.                                                   | 3                   |
| 3  | Write `scout/extractors/x.py::XExtractor`.                                                 | 2                   |
| 4  | Register XExtractor + XSource in `scout/agent/runner.py`.                                  | 3                   |
| 5  | Flip `scout/sources/x-handles.yaml` to `enabled: true` (only if proceeding).               | 4                   |
| 6  | Update `conventions/security.md` with bearer-token-location rule.                          | 7                   |
| 7  | Update `docs/runbooks/scout-run.md` with bearer setup + rotation.                          | 6                   |
| 8  | Unit tests: keyword filter, since_id, URL expansion, adversarial input.                    | 9                   |
| 9  | Integration test: end-to-end with mocked X API + queue → Phase 4 handoff.                  | 8                   |
| 10 | Quality gate: `uv run ruff check`, `uv run pytest`.                                        | 11                  |
| 11 | Commit as one logical change. Flip plan status to `done`; finalise `locked_decisions:`. Rename session prompt to `phase-5-x-twitter.done.md`. |

## Quality gate (must all pass before commit)

```sh
uv run ruff check scout/ tests/
uv run pytest -q
uv run pytest tests/integration -q
```

If we proceed with paid access, a manual smoke against the real API is
also required (one tick, verify ≥1 candidate queued and bearer not logged
anywhere).

## Commit message (template for task 11)

```
Phase 5: X / Twitter ingestion (or: deferred — choose at commit)

- scout/extractors/x.py: XExtractor — per-handle pull, since_id cursor,
  keyword + URL filter, one Candidate per github URL or per post.
- scout/agent/types.py: + XSource.
- scout/agent/runner.py: register XExtractor + XSource.
- scout/sources/x-handles.yaml: enabled: true (or stays false if deferred).
- conventions/security.md: bearer token rule (lives outside repo).
- docs/runbooks/scout-run.md: bearer setup + rotation.
- docs/plans/phase-5-x-twitter.md: status -> done; locked decisions finalised.
- docs/plans/session_prompts/phase-5-x-twitter.done.md: archived.
```

## When this plan becomes stale

Status flips to `done` when the commit lands. If we deferred X (option c)
and a later phase revisits the decision (paid access becomes viable, or a
third-party aggregator stabilizes), write a new plan that `supersedes:
[phase-5-x-twitter]` rather than reopening this one.
