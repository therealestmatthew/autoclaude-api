---
name: convention-frontmatter
title: "Convention — Frontmatter and sidecars"
kind: convention
status: active
created_at: 2026-06-14
updated_at: 2026-06-15
---

# Frontmatter

YAML frontmatter is the structured layer over our content. It is how the **manifest scanner** (`uv run manifest`) discovers what's in the repo and what state it's in.

## Universal rule

**Every document in the repo has YAML frontmatter (markdown) or a YAML sidecar (binary).**

- A `.md` or `.markdown` file → frontmatter at the top, delimited by `---` lines.
- A binary or non-text "document" (`.pdf`, `.docx`, `.pptx`, `.xlsx`, `.png`, `.jpg`, `.jpeg`, `.svg`, `.zip`, `.csv`, `.tsv`, audio, video) → a sibling file `<filename>.<ext>.meta.yaml` containing the same frontmatter shape (no leading `---` delimiters; it's already YAML).
- A non-document text file (Python source, YAML config, TOML, JSON, lockfile, LICENSE, `.gitignore`, etc.) is **not** a document and does not need frontmatter.

The manifest scanner walks `git ls-files`, classifies each tracked path by extension, and reports missing-frontmatter / missing-sidecar entries. See `tools/manifest.py`.

### What counts as a "document"

A document is anything written for a human reader as the primary purpose. Tests, code, and config aren't documents even when they contain prose comments. Generated artefacts (e.g., `MANIFEST.md` itself) **are** documents and carry frontmatter — they just declare `generated_by:` so the scanner knows not to flag them for manual edit.

## Minimum common fields

Every document (regardless of type) carries at least:

| Field         | Type    | Notes                                                                                  |
| ------------- | ------- | -------------------------------------------------------------------------------------- |
| `name`        | string  | Kebab-case identifier. For catalog assets, this is the slug and equals the filename.   |
| `title`       | string  | Human-readable title.                                                                  |
| `status`      | enum    | Per-type values listed below. Default for new content: `draft`.                        |
| `updated_at`  | date    | ISO `YYYY-MM-DD`. Bump on every meaningful edit.                                       |

Plus whichever per-type fields the document's role requires (see below).

## Per-type extensions

Different document types extend the minimum with their own fields. Each type has a canonical schema, linked from here:

| Document type                | Schema / spec                                  | Distinguishing fields                                                        |
| ---------------------------- | ---------------------------------------------- | ---------------------------------------------------------------------------- |
| Catalog asset                | `/catalog/_schema/asset.schema.md`             | `kind`, `source`, `discovered`, `relations`, `fingerprint`                   |
| Scout queue candidate        | (subset of catalog asset)                      | `kind`, `source`, `discovered` — `status: draft` implicit                    |
| Engagement folder root       | (see below)                                    | `client`, `started_on`, `ended_on`, `sow_url`, `primary_contact`             |
| Methodology                  | `/consulting/methodologies/README.md`          | `applies_to.engagement_types`, `version`                                     |
| Template                     | `/consulting/templates/README.md`              | `placeholders`, `version`, `publish`, `applies_to.engagement_types`          |
| Plan                         | `/docs/plans/README.md`                        | `phase`, `completed_at`, `supersedes`, `superseded_by`, `locked_decisions`   |
| Session prompt               | `/docs/plans/README.md`                        | sibling of a plan; `kind: session-prompt`; `status` flips to `done` when archived as `.done.md` |
| Runbook                      | `/command-center/runbooks/README.md` / `/docs/runbooks/README.md` | `when_to_run`, `last_used`, `last_verified`              |
| Convention                   | (this file)                                    | `kind: convention`                                                           |
| README (directory index)     | n/a — short canonical shape below              | `kind: readme`                                                               |
| Generated document           | n/a — short canonical shape below              | `generated_by`, `generated_at`                                               |

### README minimum

Every directory has a `README.md` and every `README.md` carries:

```yaml
---
name: <dir-slug>-readme            # e.g. consulting-templates-readme
title: "<Directory display name>"
kind: readme
status: active                     # active | stub | retired
updated_at: 2026-06-15
---
```

Stub READMEs (e.g., `/consulting/positioning/README.md`) use `status: stub` so the manifest can surface them.

### Generated document minimum

```yaml
---
name: manifest
title: "Repository manifest"
kind: generated
status: active
generated_by: tools/manifest.py
generated_at: 2026-06-15T08:14:22Z
updated_at: 2026-06-15
---
```

Generated docs are committed (so diffs surface changes) but should not be edited by hand — the scanner warns if `generated_at` is older than the most-recent input mtime.

## Status values by document type

| Type                | Allowed `status` values                                  |
| ------------------- | -------------------------------------------------------- |
| Catalog asset       | `draft` · `reviewed` · `adopted` · `archived`            |
| Scout queue candidate | implicit `draft`                                       |
| Engagement root     | `prospecting` · `active` · `paused` · `completed`        |
| Methodology         | `draft` · `active` · `retired`                           |
| Template            | `draft` · `active` · `retired`                           |
| Plan                | `draft` · `active` · `done` · `superseded`               |
| Session prompt      | `draft` · `active` · `done` · `superseded`               |
| Runbook             | `draft` · `active` · `stale` · `retired`                 |
| Convention          | `draft` · `active` · `retired`                           |
| README              | `active` · `stub` · `retired`                            |
| Generated           | `active` · `stale`                                       |

Status enums are validated by the manifest scanner against this table. Adding a value requires editing both this table and `tools/manifest.py`.

## Sidecar files for binary documents

For each binary document `path/to/file.<ext>`, place a sibling file `path/to/file.<ext>.meta.yaml`:

```yaml
# file.pdf.meta.yaml — no leading --- delimiters; the whole file is YAML.
name: q3-board-deck
title: "Q3 board deck"
kind: deck
status: active
updated_at: 2026-06-15
source_url: ""               # if originated externally
notes: >
  Optional human-readable context. The PDF itself is the artefact;
  this file exists so the manifest can track it.
```

Sidecars carry the same minimum fields as in-file frontmatter, plus whatever per-type fields apply. The scanner treats a binary document with **no** sidecar as missing-frontmatter and lists it for backfill.

## Catalog asset — full spec

The authoritative spec lives in `/catalog/_schema/asset.schema.md`. Summary of required vs optional below.

### Required (catalog asset)

| Field        | Type     | Notes                                                              |
| ------------ | -------- | ------------------------------------------------------------------ |
| `name`       | string   | The slug. Identity. See `naming.md`.                               |
| `kind`       | enum     | One of the values in `kinds.md`.                                   |
| `title`      | string   | Human-readable title.                                              |
| `status`     | enum     | `draft` \| `reviewed` \| `adopted` \| `archived`.                  |
| `source`     | object   | `type`, `url`, plus author/license where known.                    |
| `discovered` | object   | `via`, `on`, optional `run_id`. How we found it.                   |
| `created_at` | date     | ISO `YYYY-MM-DD`.                                                  |
| `updated_at` | date     | ISO `YYYY-MM-DD`. Update on every meaningful edit.                 |

### Optional but encouraged (catalog asset)

| Field         | Type    | Notes                                                                 |
| ------------- | ------- | --------------------------------------------------------------------- |
| `quality`     | 1–5     | Our judgment after review. Omit until reviewed.                       |
| `tags`        | list    | Free-form, kebab-case. Used for filtering and merge hints.            |
| `relations`   | object  | `parent`, `related[]`, `supersedes[]`.                                |
| `fingerprint` | string  | Hash of source content; used by scout for change detection.           |

### Body

Everything below the closing `---` is our own notes: why we kept it, how we use it, gotchas, integration steps. The body is for our judgment; the frontmatter is for facts.

## Scout queue candidate

A subset of the catalog shape — anything we know at discovery time. `status: draft` is implicit. Review converts a candidate to a full catalog asset.

Required: `name` (best-guess slug), `kind` (best-guess), `title`, `source`, `discovered`. Everything else can wait.

## Engagement folder root

`/consulting/engagements/<year>-<client>/README.md` carries frontmatter:

```yaml
---
name: 2026-acme-co
title: "Acme Co — feature build (2026)"
kind: engagement
client: acme-co
status: prospecting | active | paused | completed
started_on: 2026-06-14
ended_on:                       # set when completed
sow_url:                        # link to signed SOW
primary_contact:                # name + role
updated_at: 2026-06-14
---
```

## Dates

- Always ISO `YYYY-MM-DD` for date fields; ISO 8601 with timezone for timestamps (`generated_at`).
- When recording a date a user said in natural language ("Thursday", "next week"), convert to absolute before writing.

## Backfill posture

Existing files without frontmatter are not blockers — the manifest scanner reports them as a punch list. New files (created from this convention forward) must comply. Backfill happens opportunistically when a file is edited for unrelated reasons, or in dedicated passes when the gap list is short enough to clear.
