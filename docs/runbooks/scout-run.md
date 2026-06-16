---
name: scout-run
title: "Run the scout and review the queue"
when_to_run: "Whenever you want fresh discovery candidates from HN, Lobsters, Reddit, or curated awesome-lists — typically daily, but the cursors keep state so a missed day just means a bigger next batch. Also covers `scout extract-repo` for ad-hoc child-asset extraction from one GitHub repo."
last_used:
last_verified: 2026-06-15
---

# Run the scout

The scout polls configured sources, dedups against `/catalog/`, and writes one
markdown file per surviving candidate to `/scout/queue/`. You then review the
queue by hand and either merge candidates into `/catalog/` or discard them.

This runbook covers the full loop: setup → run → review → cleanup.

---

## 0. One-time setup

```sh
# In the repo root.
uv sync
```

This creates `.venv/` and installs runtime + dev dependencies. Re-run after
pulling a commit that changes `pyproject.toml` or `uv.lock`.

You don't activate the venv by hand — every command below uses `uv run`,
which evaluates against the project venv each time.

**Verify.** `uv run scout --help` prints usage without error.

---

## 1. Run the scout

### 1a. All enabled sources

```sh
uv run scout run -v
```

**Expected output (shape):**

```
[scout] <N> URLs known to catalog
[scout] hackernews: queued=<X> skipped_catalog=<Y>
[scout] lobsters:   queued=<X> skipped_catalog=<Y>
[scout] reddit:     queued=<X> skipped_catalog=<Y>
[scout] awesome-lists: queued=<X> skipped_catalog=<Y>
scout-<YYYY-MM-DD>-<HHMMSS>: queued=<TOTAL> skipped_catalog=<TOTAL> errors=0
```

Exit code is `0` on success, `1` if any per-source error landed in the
top-level stats `errors` list.

### 1b. One source at a time

Useful when you're iterating on a single extractor or one source is rate-
limiting and you don't want to retry the others.

```sh
uv run scout run -s hackernews -v
uv run scout run -s lobsters -v
uv run scout run -s reddit -v
uv run scout run -s awesome-lists -v
```

The slug matches the YAML filename stem in `/scout/sources/<slug>.yaml`.

### 1b'. Extract one GitHub repo by hand

`scout extract-repo` clones a single GitHub repo inside a per-clone Docker
container, walks the allowlisted paths (see `conventions/security.md`),
and writes one queue file per child asset (agent, skill, plugin, mcp,
prompt) it finds. The container has network for the `git clone` step only;
nothing from the repo is ever executed.

```sh
# Pass either a full URL or org/repo shorthand:
uv run scout extract-repo anthropics/claude-cookbooks
uv run scout extract-repo https://github.com/anthropics/claude-cookbooks -v
```

**Expected output (shape):**

```
scout-extract-<YYYY-MM-DD>-<HHMMSS>: children_queued=<N> warnings=<W>
```

Each child queue file has `relations.parent: <repo-slug>`, a
`fingerprint: sha256:<hex>` over the upstream file bytes, and a
`source.url` pointing at `https://github.com/<org>/<repo>/blob/<commit-sha>/<relpath>`.

**Prerequisites.**

- Docker daemon running and accessible to your user (`docker info` works).
  Podman is not yet supported (`--runtime podman` raises NotImplementedError).
- The `scout-clone-runner` image. If it isn't present, you'll see a
  `ContainerError` — build it once with:
  ```sh
  docker build -t scout-clone-runner scout/clone_runner/
  ```

**The queue-driven path runs automatically.** When `scout run` surfaces a
new `kind: repo` candidate (e.g. from awesome-lists), the same tick walks
the queue for unreviewed github-typed repo entries and runs the extractor
on each. To skip a repo permanently, delete the parent queue file before
the next run.

### 1b''. Run the dedup engine on demand

`scout dedup` runs four deterministic passes over `/scout/queue/` and
`/catalog/` and surfaces merge recommendations without touching catalog
content beyond the four allowlisted status fields. The same pass also runs
at the tail of every `scout run` unless `--no-dedup` is passed.

```sh
uv run scout dedup                    # all four passes; writes/deletes apply
uv run scout dedup --dry-run -v       # report what would change; touch nothing
uv run scout dedup --pass identity    # one pass at a time (debug)
uv run scout dedup --pass proposals
```

**Expected output (shape):**

```
dedup-<YYYY-MM-DD>-<HHMMSS>: identity=<X> url=<Y> proposals=<Z> auto_archived=<A>
```

After it runs:

- Some queue files may be **gone** (identity / URL-canonical collapse).
- Some queue files have a new `mergeset_id: ms-<sha8>` frontmatter field
  and a `## Merge proposal (auto)` body section recommending a target.
- A few catalog files may flip to `status: archived` with an
  `archived_reason` (`source-url-404` or `superseded`) and an `archived_at`.

To reject a proposal, change its body header from
`## Merge proposal (auto)` to `## Merge proposal (auto, rejected)`. The
engine records the rejection in `/scout/state/merge-decisions.json` and
will not re-propose it.

See `/conventions/merge-rules.md` for the full automation contract.

### 1c. Force a "from-scratch" run

Cursors live in `/scout/state/<source>.json`. Delete the file for the
source(s) you want to reset and the next run starts from the beginning of
each source's history (or as far back as the source itself exposes).

```sh
rm /scout/state/hackernews.json   # reset the HN cursor only
```

**Warning.** This will re-queue every previously-seen candidate that the
source still returns. Expect a large queue on the next run. The catalog
dedup will still suppress anything already in `/catalog/`, but you'll have
to triage everything else again.

---

## 2. Review the queue

Candidates land in `/scout/queue/<date>-<slug>-<hash>.md`. Each file is
self-contained — frontmatter has provenance, body is reviewer notes.

### 2a. Skim the queue

```sh
ls /scout/queue/ | wc -l                          # how many
ls -t /scout/queue/ | head -20                    # most recent
```

### 2b. Skim the dedup output first

The dedup pass ran at the end of the most recent `scout run`. Before opening
queue files one by one, look at what it already grouped:

```sh
# How many active merge proposals
grep -l "scout-dedup-proposal-start" /scout/queue/*.md | wc -l

# How many catalog items were auto-archived in the last day
grep -l "archived_at: $(date -I)" /catalog/*.md
```

Files with `mergeset_id:` frontmatter belong to an active group; reviewing
one member often resolves the rest. Files without a mergeset are
genuinely-distinct candidates.

### 2c. Open and decide

Open one queue file at a time. For each:

1. Read the title and `source.url`. Does this look like an artifact we'd
   want in `/catalog/`?
2. Click through to `scout.raw_url` if you need discussion context.
3. Decide:
   - **Keep** → write a `<slug>.md` in `/catalog/` (use `/catalog/_schema/`
     and `/catalog/_examples/` as references). See
     `/conventions/merge-rules.md` for whether to create new or merge into
     an existing asset.
   - **Discard** → just `rm` the queue file.
   - **Merge** → update the existing `/catalog/<slug>.md` (add an alternate
     URL, bump tags, etc.), then `rm` the queue file.

### 2d. Inspect what the candidate looks like

```sh
cat /scout/queue/<file>.md
```

Frontmatter you can trust the scout to have filled in:

- `name`, `kind`, `title`, `status: draft`
- `source.{type,url}` — the artifact's primary URL
- `discovered.{via,on,run_id}` — provenance
- `scout.raw_url` — discussion or list URL (e.g. the HN item, the Lobsters
  thread, the Reddit permalink)
- `scout.score` (HN/Reddit only) — original platform score, useful for
  prioritization

Everything else (tags, source.authors beyond the first, source.license,
relations) is up to the reviewer.

---

## 3. Clean up the queue

Once you've reviewed everything, the queue should be empty (or contain only
items you want to defer). The queue itself is gitignored — only the
`README.md` and `_template.md` are tracked.

```sh
ls /scout/queue/ | grep -v -E '^(README|_template)\.md$' | wc -l
```

Expected: `0` after a full review pass.

---

## Troubleshooting

### `403 Blocked` from Reddit

Seen on every sub when running from a residential / cloud IP without auth.
Reddit's anti-scraping is hostile to anonymous `*.reddit.com/r/<sub>/new.json`
requests.

**Verify.** Check `/scout/state/reddit.json` — the errors are recorded under
`stats.sub_errors`, the run still completes with `outcome: ok` because the
extractor swallows the per-sub HTTP error rather than blowing up the run.

**Workarounds (not yet implemented):**

- Set up OAuth via Reddit's "script" app type and route the extractor
  through `https://oauth.reddit.com/`.
- Switch the extractor to a public mirror or a different listing API.

Until one of those lands, `scout run -s reddit` is expected to queue 0.
Don't treat it as a regression.

### Lobsters queues 0

Most days the strict keyword filter (`claude code`, `claude-code`,
`anthropic`, `mcp server`, `agent sdk`) doesn't match anything in
`/t/ai.rss` or `/t/programming.rss`. This is the source being low-volume,
not a bug.

**Verify.** `curl -s -A "autoclaude-scout/0.1.0" https://lobste.rs/t/ai.rss
| grep -oE '<title>[^<]*</title>' | head -20` lists current titles. If none
of them contain a keyword from `scout/sources/lobsters.yaml`, queue=0 is
correct.

**Loosen the filter** by editing `match.any_of` in `scout/sources/lobsters.yaml`
— but expect higher noise.

### HN queued thousands on the first run

Expected. The HN Algolia API returns up to 100 hits per query term, the
default config has ~8 terms, and on a cold cursor every hit qualifies. The
cursor advances to the highest `created_at_i` seen, so the next run is
small.

If you want a smaller first batch, raise `min_points` in
`scout/sources/hackernews.yaml` temporarily, then lower it back.

### `UnsafeURLError` / `ResponseTooLargeError` in the per-source state

These come from `scout/_security.py` rejecting an unsafe URL (e.g. a
redirect to a private IP) or a response that exceeds the byte cap. They are
recorded in the per-source `state.stats` (`list_errors`, `term_errors`,
`feed_errors`, `sub_errors` depending on the extractor) and **do not** halt
the run. The catalog will simply not get the rejected item.

**Verify.** Look at `/scout/state/<source>.json` and the per-source error
list. If the URL there is one you trust, investigate the redirect chain;
otherwise the rejection is correct behavior.

### Exit code 1 from `scout run`

The runner returns `1` if any *top-level* error landed in `stats.errors` —
usually a source whose YAML had an unknown `type:`. Per-source extractor
errors (HTTP, parse, security) are recorded inside per-source state and
**do not** trigger exit 1; the run is still considered "partial-ok".

```sh
uv run scout run -v
echo $?     # 0 = clean, 1 = top-level error
```

If you see `1`, the stderr lines starting with `!` name the failing source.
Check that the YAML's `type:` matches a key in `EXTRACTOR_REGISTRY` in
`scout/agent/runner.py`.

---

### `ContainerError: docker not on PATH` from `extract-repo`

`scout/_container.py` checked `shutil.which("docker")` and the binary was
absent. Install Docker (or invoke an extractor that doesn't need it). The
podman runtime is reserved (`--runtime podman` raises
`NotImplementedError`) until Phase 6 revisits the rootless story.

### `ContainerError: clone-runner exited <n>` from `extract-repo`

The clone-runner container exited nonzero. The first ~500 chars of stderr
are included in the error string; common causes:

- The image isn't built locally. Run
  `docker build -t scout-clone-runner scout/clone_runner/`.
- `git clone` failed (404, auth-required, or network). The repo URL is
  reported in the error; check it.
- A symlink was found inside the allowlisted dirs. The clone-runner aborts
  with exit 2 in that case — treat the repo as hostile.

## What this runbook does NOT cover

- **Promoting a queue item to `/catalog/`.** See `/conventions/merge-rules.md`
  and `/catalog/_schema/asset.schema.md`.
- **Adding a new source.** Add the YAML in `/scout/sources/`, write an
  extractor, register it in `scout/agent/runner.py`. See the Phase 3 commit
  (`be5809a`) for the full pattern.
- **Operating the system (rotating credentials, restoring state from
  corruption).** Those runbooks live in `/command-center/runbooks/`.
