# Security

The scout ingests untrusted content from public sources and (Phase 4) will
clone arbitrary GitHub repositories. This document captures the threats we
defend against and the rules that make those defenses load-bearing.

This is the **minimum set of rules** that keep the catalog and any future
agent context safe from adversarial content on the public internet. Threats
specific to authenticated services, secret management, or enterprise
compliance are out of scope until we have a reason to add them.

## Threat model

### 1. Prompt injection via scraped content

Any title, description, README, or skill/agent definition we pull becomes
context that a future agent (or future Claude session) may read. A malicious
entry can carry:

- Literal jailbreak strings ("ignore previous instructions…").
- Hidden Unicode: bidirectional overrides (U+202A–202E, U+2066–2069),
  zero-width chars (U+200B–200F, U+FEFF), private-use area characters,
  surrogate halves, unassigned codepoints.
- HTML-style "instructions in a comment" (`<!-- when you see this… -->`).

**Defense.** Sanitize on ingest: strip control + bidi + zero-width chars,
normalize Unicode to NFC, collapse runs of whitespace, length-cap each field.
The human reviewer is the current gate; **if we ever add an agent reviewer,
this document gets a new section first** spelling out delimited-input rules
and a no-tools sandbox for that agent.

### 2. Code execution via cloned repos (Phase 4)

Default assumption: every repo we clone is hostile.

**Defense.** Phase 4 clones in a **per-clone Docker / podman container** with
no network and a tmpfs. Inside the container:

- `git clone --depth 1 --no-tags --filter=blob:none --no-recurse-submodules`.
- Static parsing only — **never execute** anything from the repo. No
  `pip install`, no `python setup.py`, no test runs, no Python imports of
  repo modules.
- Read only files within an allowlist of paths (`.claude/`, `skills/`,
  `agents/`, `mcp.json`, `README*`, `LICENSE*`, top-level `.md`).
- Resolve every path and reject anything that escapes the clone root via
  symlink.
- Hard caps: per-file 1MB, total clone 100MB, file count 5000.

The container is the boundary; the rules inside it are defense in depth.

### 3. Network and parser attacks

- **SSRF.** A misconfigured source endpoint or a malicious redirect can land
  on a private IP, leaking internal data or hitting cloud metadata services
  (e.g. `169.254.169.254`). **Defense:** `safe_external_url` rejects
  loopback / private / link-local hosts both pre-request and after every
  redirect.
- **Resource exhaustion.** A 100MB RSS feed will OOM us. **Defense:**
  `safe_get_bytes` streams with a hard byte cap (10MB default).
- **XML attacks.** XXE, billion-laughs, and friends. **Defense:** all XML
  parsing goes through `defusedxml`. Never `xml.etree.ElementTree` directly.

## Module: `scout/_security.py`

The toolkit. Pure functions plus one thin HTTP wrapper.

| Symbol                          | Purpose                                                                         |
| ------------------------------- | ------------------------------------------------------------------------------- |
| `sanitize_text(s, max_length=)` | Strip dangerous chars, NFC-normalize, collapse whitespace, length-cap.          |
| `safe_external_url(url)`        | True iff URL is http(s) and host is **not** loopback / private / link-local.   |
| `safe_get_bytes(client, url, …)`| URL-validated GET that streams with a byte cap and re-checks final URL.        |
| `UnsafeURLError`                | Raised when `safe_external_url` returns False, before or after redirect.       |
| `ResponseTooLargeError`         | Raised when a streamed response would exceed `max_bytes`.                      |

## Rules

1. **Every extractor uses `safe_get_bytes` for HTTP** — never `client.get()`
   directly. The HTTP client is still injectable for testing; only the
   *transport* changes.
2. **Every extractor calls `sanitize_text` on free-form fields** before
   yielding a `Candidate`. Default caps:
   - `title` — 300
   - `author` — 100
   - `excerpt` — 2000
3. **XML parsing goes through `defusedxml`.** No bare `xml.etree.ElementTree`
   in production code.
4. **Repo cloning (Phase 4) happens in a per-clone container.** No exceptions.
5. **We never execute downloaded content.** Static parsing only.
6. **The human is the gate.** Phase 1 catalog promotion is human-only. If
   that changes, this section changes first.

## Review checklist for a new extractor

Before merging a new extractor, the PR must:

- [ ] Use `safe_get_bytes` for every HTTP call.
- [ ] Call `sanitize_text` on every free-form string that ends up in a
      `Candidate`.
- [ ] Have at least one unit test feeding adversarial input — a bidi/zero-width
      character in a title, an oversized payload, or a private-IP URL — and
      asserting the right rejection or sanitization.
- [ ] Not introduce a new XML parser without going through `defusedxml`.
- [ ] Not introduce any code path that executes downloaded content.

## What this document is not

- Not a substitute for code review.
- Not a comprehensive security policy.
- Not a place for hypothetical defenses we haven't actually wired up.

If we add a new defense (rate limiting, signed-content verification, etc.),
that defense gets its own row in the table above and a rule under "Rules" —
otherwise it doesn't exist.
