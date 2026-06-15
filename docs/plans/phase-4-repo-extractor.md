---
name: phase-4-repo-extractor
title: "Phase 4 — Repo extractor"
phase: 4
status: done
created_at: 2026-06-15
updated_at: 2026-06-15
completed_at: 2026-06-15
supersedes: []
superseded_by:
locked_decisions:
  - "Sandbox: per-clone container (Docker default; podman supported via config). Set in Phase 3."
  - "Reviewer trust model: human-only, forever. Set in Phase 3."
  - "Static parsing only inside the container. Never execute downloaded content. Set in Phase 3."
  - "Repo extraction is queue-triggered, not poll-triggered. Set here."
  - "Child slug convention: <repo-slug>--<child-name>. Set here."
  - "Child Candidates land in /scout/queue/, never directly in /catalog/. Set here."
  - "Default container runtime: Docker only in v1. Podman is a flag stub that raises NotImplementedError (compose_command rejects it). Revisit in Phase 6."
  - "Image distribution: local build only (`docker build scout/clone_runner/`). No registry dependency. RepoExtractor expects the image to be present locally; users build once."
  - "Temp dir: `tempfile.TemporaryDirectory(prefix='scout-clone-')`. No leftover state on crash; no `tmp/scout/clones/` under the repo."
  - "mcp.json parsing: one Candidate per `mcpServers` entry with slug `<repo>--mcp-<server-name>`. A generic mcp.json with no recognized servers map falls back to a single `<repo>--mcp` Candidate."
  - "Plugin repos are leaf assets: we do NOT recurse into them to emit children of children. Plugin contents are described in the plugin asset body. Re-examine in Phase 6 if needed."
  - "Container `/tmp` is on the read-only root FS; the entrypoint uses `mktemp -p /work` (the tmpfs) for its scratch files. Captured here because it's an easy-to-regress detail."
---

# Phase 4 — Repo extractor

## Goal

Given a GitHub repo (already in the catalog as `kind: repo`, or surfaced into `/scout/queue/` by a Phase 2/3 extractor), produce zero or more child-asset Candidates (`kind` ∈ `{agent, skill, plugin, mcp, prompt}`), each carrying `relations.parent: <repo-slug>` and full provenance back to the file in the repo at a pinned commit SHA.

Output of the phase: the agent toolkit grows from scout output instead of from manual catalog edits. Closes the discovery → extraction → review → adoption loop.

## Non-goals (out of scope for this phase)

- Discovering repos directly from GitHub. Discovery still flows from socials + awesome lists; this phase only *extracts from* repos already surfaced by other extractors.
- Auto-promoting child Candidates to `/catalog/`. Human review remains the gate.
- Cloning private repos, repos requiring auth, or running anything from the repo.
- DNS-resolution-based SSRF defense (still tracked as a follow-up from Phase 3).
- X / Twitter ingestion (Phase 5).
- Automated merge/dedup decisioning (Phase 6).

## Constraints (inherited)

From `conventions/security.md`:

- **Per-clone container.** Every clone runs in a fresh, throwaway container with no persistent state. The container is the boundary; the rules inside it are defense in depth.
- **Static parsing only.** No `pip install`, no `python -m`, no test runs. Read files, parse markdown/YAML/JSON, that's it.
- **Path allowlist.** Only `.claude/`, `skills/`, `agents/`, `mcp.json`, `README*`, `LICENSE*`, top-level `*.md`.
- **Symlink rejection.** Resolve every path; if it escapes the clone root, reject the *entire repo* and log a security event.
- **Hard caps.** Per-file 1 MB, total clone 100 MB, file count 5000. Cap exceeded → emit partial result *with* a warning in the thread record; never silently truncate.
- **Sanitization.** Every free-form string that ends up in a Candidate runs through `scout/_security.py::sanitize_text` with appropriate length cap.
- **No bare XML.** Continue using `defusedxml` (no XML expected in this phase, but the rule stands).

## Design

### Trigger

Two ways the extractor runs:

1. **Manual:** `uv run scout extract-repo <github-url-or-repo-slug>`. For ad-hoc curation. Writes child Candidates to `/scout/queue/` with `discovered.via: manual`.
2. **Queue-driven:** during a `scout run` tick, after the existing extractors emit Candidates, the runner scans `/scout/queue/` for unreviewed entries with `source.type: github` and `kind: repo`. For each, it invokes the repo extractor and emits children Candidates carrying the parent repo's `discovered.via`.

Phase 4 ships the manual command first (smaller test surface), then wires the queue-driven path.

### Container

Two-step entrypoint inside one container run. **The container has network for the clone step and only the clone step.** Parsing happens host-side on the extracted tar.

```
Image: scout-clone-runner
  base: alpine:latest
  installs: git, bash, tar, coreutils
  user: nonroot (uid 65532)
  workdir: /work

Run flags (host):
  docker run --rm \
    --network bridge \                    # network for git only
    --read-only \
    --tmpfs /work:size=120m,uid=65532 \   # 120m gives headroom over 100m cap
    --memory 512m --cpus 1 \
    --cap-drop ALL \
    --security-opt no-new-privileges \
    --pids-limit 256 \
    -e REPO_URL=<sanitized-url> \
    scout-clone-runner

Entrypoint:
  1. git clone --depth 1 --no-tags --filter=blob:none --no-recurse-submodules \
       "$REPO_URL" /work/clone
  2. cd /work/clone
  3. record commit SHA: git rev-parse HEAD
  4. walk allowlist; for each match, check size cap; assemble tar of allowlisted
     files plus a manifest.json (relpath, size, sha256, commit_sha, repo_url)
  5. write tar to stdout; exit
```

Container responsibilities end at "tar on stdout". The host:

- Runs the container with a timeout (5 min default).
- Reads the tar into memory (capped 100 MB).
- Extracts into a host-side temp dir under `tmp/scout/clones/<run-id>/<repo-slug>/`, **re-validating** path allowlist and symlink safety on extraction (defense in depth — never trust container output blindly).
- Parses for child assets.
- Cleans up temp dir on exit.

### Asset detection rules

Walked in this order; first match wins per file:

| Path pattern                                  | Emits      | Notes                                                                  |
| --------------------------------------------- | ---------- | ---------------------------------------------------------------------- |
| `.claude/agents/**/*.md`                      | `agent`    | One agent per file. Slug from filename minus `.md`.                    |
| `.claude/skills/**/SKILL.md`                  | `skill`    | One skill per containing directory. Slug from directory name.          |
| `.claude/plugins/**/plugin.json`              | `plugin`   | One plugin per containing directory.                                   |
| `.claude/mcp.json`                            | `mcp`      | One per repo; slug `<repo-slug>--mcp`.                                 |
| `mcp.json` (top-level)                        | `mcp`      | Same.                                                                  |
| `skills/**/SKILL.md`                          | `skill`    | Non-namespaced convention; still emitted.                              |
| `agents/**/*.md`                              | `agent`    | Non-namespaced convention.                                             |
| `prompts/**/*.md`                             | `prompt`   | Conservative — only emit when frontmatter has `kind: prompt` or `purpose:`. |
| `README*`                                     | (metadata) | Used to enrich the parent repo Candidate (title, excerpt).             |
| `LICENSE*`                                    | (metadata) | First-line scan for SPDX-ish identifier; fills `source.license`.       |
| top-level `*.md`                              | (metadata) | Reserved; no child emitted by default.                                 |

A repo with zero matches still produces a thread record (so we know we tried) but no Candidates beyond the metadata-refresh on the parent.

### Slug scoping

Child slugs must be globally unique across `/catalog/`. Convention introduced here, added to `conventions/naming.md` in this phase:

```
<repo-slug>--<child-name>
```

- Double-dash separator distinguishes the scoping from intra-name dashes.
- `child-name` is the kebab-cased filename (for `agent`/`prompt`) or directory name (for `skill`/`plugin`).
- Collisions inside the same repo (two `agents/foo.md` and `.claude/agents/foo.md`) → reject the second and log a warning. We do not auto-disambiguate.

### Fingerprinting

Two layers:

- **Repo fingerprint:** `sha256(clone-commit-sha)`. Stored on the repo Candidate / catalog asset. Unchanged → skip extraction entirely.
- **Child fingerprint:** `sha256(file-bytes)`. Stored on each child. Used by Phase 6 to detect upstream changes that warrant re-emission.

### Output: Candidate frontmatter

Per child:

```yaml
---
name: <repo-slug>--<child-name>
kind: <detected>
title: <derived from frontmatter title, README h1, or filename>
source:
  type: github
  url: https://github.com/<org>/<repo>/blob/<commit-sha>/<relpath>
  authors: [<parent-repo-source.authors>]
  license: <inherited from parent repo unless child specifies>
discovered:
  via: <parent-repo discovered.via, or 'manual'>
  on: <YYYY-MM-DD>
  run_id: <run-id>
relations:
  parent: <repo-slug>
fingerprint: sha256:<hex>
created_at: <YYYY-MM-DD>
updated_at: <YYYY-MM-DD>
---
```

### Failure modes & required handling

| Failure                                       | Action                                                                                     |
| --------------------------------------------- | ------------------------------------------------------------------------------------------ |
| Docker daemon unavailable                     | Skip this Candidate; thread record records `extractor: repo, status: skipped, reason`.     |
| `git clone` fails (404, auth, network)        | Update parent repo Candidate body with reason; no children emitted.                        |
| Clone exceeds size cap                        | Abort clone, emit warning, no children. Parent gets a note.                                |
| Symlink escape detected (container or host)   | Abort whole repo. Log `security-event: symlink-escape, repo: <slug>`.                      |
| File count > 5000                             | Abort. Log warning.                                                                        |
| Container timeout (default 5 min)             | Abort. Log warning. Don't retry automatically.                                             |
| Per-file > 1 MB                               | Skip that file. Continue.                                                                  |
| Path outside allowlist after extraction       | Skip that file (defense in depth even if container should have filtered).                  |
| Duplicate child slug within same repo         | Emit first; log warning for the second.                                                    |
| Existing catalog asset with same `source.url` | Don't emit a new queue file. Bump `updated_at` on the existing asset only if fingerprint changed. |

## Code surface (rough)

New files:

```
scout/
  clone_runner/
    Dockerfile               minimal alpine + git
    entrypoint.sh            clone + allowlist walk + tar to stdout
    README.md                what this image is, how to build it
  extractors/
    repo.py                  RepoExtractor — orchestrates container + parses tar
  agent/
    types.py                 + RepoExtractRequest, ChildCandidate
    runner.py                + queue-driven invocation (after primary extractors)
    cli.py                   + extract-repo subcommand
  _container.py              thin wrapper: run docker/podman with our locked flags
```

Updated files:

```
conventions/naming.md        + child-slug convention (<repo>--<child>)
conventions/security.md      + container-flags reference; reaffirms host re-validation
scout/sources/README.md      + note that repos are extraction targets, not a source
docs/runbooks/scout-run.md   + section on extract-repo and reviewing children
```

New tests (per `conventions/testing.md`):

```
tests/unit/
  test_repo_extractor_paths.py        allowlist + symlink rejection
  test_repo_extractor_slugs.py        scoping + collision behavior
  test_repo_extractor_fingerprint.py  hashing + skip-on-unchanged
  test_container_wrapper.py           flag composition (no real docker invoked)
tests/integration/
  test_repo_extract_e2e.py            fixture tarball stubbed as if from container;
                                      asserts Candidate emission, file layout, sanitization
tests/fixtures/repo-clones/
  minimal-with-agent/                 a synthesized "clone" layout
  minimal-with-skill/
  hostile-symlink/                    symlink that escapes root
  oversize/                           > 1 MB file
```

Live smoke (manual, post-implementation):

```
uv run scout extract-repo anthropics/claude-cookbooks
uv run scout extract-repo --podman <repo>
```

Both must produce queue entries; no host-side execution of repo contents must occur (verify with `strace -f` or audit `ps` during the run).

## Open questions to resolve during the session

1. **Default container runtime.** Docker is the lock; do we also ship a podman code path on day one, or behind a `--runtime` flag with Docker hardcoded for v1? *Recommendation: Docker only in v1; podman support is a flag stub that raises `NotImplementedError`.*
2. **Image distribution.** Build locally on first invocation (`docker build scout/clone_runner/`) vs publish a pinned image? *Recommendation: local build only; cache via Docker layers. No registry dependency in v1.*
3. **Where does the temp dir live?** `tmp/scout/clones/` under repo root (gitignored) or `tempfile.TemporaryDirectory()`? *Recommendation: `TemporaryDirectory()` — no risk of leftover state surviving a crash.*
4. **`mcp.json` parsing.** Many forms in the wild (Claude Code project config, generic MCP server descriptor, etc.). Do we emit one `mcp` Candidate per server entry, or one per file? *Recommendation: one per server entry; slug `<repo>--mcp-<server-name>`.*
5. **What about `claude-plugin` repos** that are themselves bundles? Do we emit children of children? *Recommendation: no. A plugin is the leaf; its internal contents are described in the plugin asset body, not as separate Candidates. Re-examine in Phase 6.*

Each open question gets answered in the commit; the answer moves into `locked_decisions:` on this plan's frontmatter at phase close.

## Task breakdown (suggested execution order)

Tasks are sized so several can run in parallel via subagents. The numbers are a sequence guide for the session that runs this plan.

| #  | Task                                                                                          | Parallelizable with |
| -- | --------------------------------------------------------------------------------------------- | ------------------- |
| 1  | Update `conventions/naming.md` with the `<repo>--<child>` child-slug rule.                    | 2, 3                |
| 2  | Update `conventions/security.md` with the container-flags reference and host re-validation reaffirmation. | 1, 3 |
| 3  | Write `scout/clone_runner/Dockerfile`, `entrypoint.sh`, `README.md`.                          | 1, 2                |
| 4  | Implement `scout/_container.py` (flag composition, runtime selection, timeout wrapper).        | (alone — others depend on it) |
| 5  | Implement `scout/extractors/repo.py::RepoExtractor` (orchestrate container, read tar, extract host-side, detect assets, emit Candidates). | (depends on 4) |
| 6  | Extend `scout/agent/types.py` with `RepoExtractRequest` and any new ChildCandidate fields.    | 5                   |
| 7  | Wire `scout/agent/cli.py` `extract-repo` subcommand.                                          | 5                   |
| 8  | Wire `scout/agent/runner.py` to invoke the repo extractor on queue entries with `source.type: github`, `kind: repo`. | 5 |
| 9  | Unit tests: paths, slugs, fingerprint, container-wrapper. Use the fixture layouts.            | 5, 7, 8             |
| 10 | Integration test: end-to-end with a fixture tarball stubbed in for the container output.      | 9                   |
| 11 | Fixture clones (minimal-with-agent, minimal-with-skill, hostile-symlink, oversize).           | 9, 10 (write first) |
| 12 | Update `scout/sources/README.md` and `docs/runbooks/scout-run.md`.                             | 13                  |
| 13 | Smoke test: `uv run scout extract-repo anthropics/claude-cookbooks`; verify queue entries; verify no host-side execution. | (last) |
| 14 | Quality gate: `uv run ruff check`, `uv run pytest`, `uv run pytest tests/integration`.        | 13                  |
| 15 | Commit as one logical change. Update this plan's frontmatter: `status: done`, `completed_at`, finalise `locked_decisions`. Rename the sibling session prompt to `phase-4-repo-extractor.done.md`. |

## Quality gate (must all pass before commit)

```sh
uv run ruff check scout/ tests/
uv run pytest -q
uv run pytest tests/integration -q
# Smoke (manual):
uv run scout extract-repo anthropics/claude-cookbooks
```

The smoke must produce ≥1 queue file with `relations.parent` set and no host-side execution of repo contents.

## Commit message (template for task 15)

```
Phase 4: repo extractor with per-clone container sandbox

- scout/clone_runner/: minimal alpine + git image; entrypoint clones with
  --depth 1 --filter=blob:none, walks allowlist, tars to stdout, exits.
- scout/_container.py: locked docker/podman flag composition + timeout wrapper.
- scout/extractors/repo.py: orchestrates container, re-validates host-side,
  detects children (agent/skill/plugin/mcp/prompt), emits Candidates with
  relations.parent set and per-file sha256 fingerprints.
- scout/agent/cli.py: `extract-repo` subcommand for manual triggering.
- scout/agent/runner.py: queue-driven invocation on github-typed queue entries.
- conventions/naming.md: child-slug convention <repo>--<child>.
- conventions/security.md: container-flags reference + host re-validation rule.
- Fixture clones for unit + integration tests; hostile-symlink and oversize
  fixtures verify rejection paths.
- docs/runbooks/scout-run.md: section on extract-repo and reviewing children.
- docs/plans/phase-4-repo-extractor.md: status -> done; locked decisions finalised.
- docs/plans/session_prompts/phase-4-repo-extractor.done.md: archived.
```

## When this plan becomes stale

Status flips to `done` when the commit lands. From that point the plan is read-only history. If the design fundamentally changes later (e.g., we move to a registry-published image, or replace container-per-clone with a different sandbox), write a new plan that `supersedes: [phase-4-repo-extractor]` and set this one's `superseded_by:` accordingly.
