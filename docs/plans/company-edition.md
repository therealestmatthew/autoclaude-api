---
name: company-edition
title: "Company Edition — fork-and-pivot to a Finance Transformation practice platform"
status: draft
created_at: 2026-06-19
updated_at: 2026-06-19 (internal-tool correction)
completed_at:
supersedes: []
superseded_by:
locked_decisions:
  - "Hard fork into a private company repo; no upstream sync from autoclaude after Phase 10.0."
  - "This is an INTERNAL DELIVERY TOOL for the consulting practice — not a multi-client tenancy platform. Consultants use it to generate branded deliverables; clients never log in."
  - "Single shared instance; `client` is a lightweight lookup record (slug, name, brand_slug, engagement_context) for repeat-export convenience only — not a tenant boundary."
  - "No sensitivity tiers, cost budgets, approval workflows, or per-client access controls. Those belong in Phase 11 RBAC if ever needed."
  - "AWS deploy target is 6–12 months out; build cloud-portability seams now, defer cloud implementation to Phase 11."
  - "Keep all of Scout discovery; retarget sources to finance-relevant feeds later if useful."
  - "`Client` is a first-class DB entity, not a catalog kind (catalog assets carry mandatory provenance that clients do not have)."
  - "`Brand`, `Template`, `Bundle` are added as new catalog kinds (they have provenance, status, versioning — fit the polymorphic asset model)."
  - "`kind:` enum is split into `catalog_kind` (closed, governs `/catalog/` + `/brands/`) and `document_kind` (open, governs everything else) in Phase 10.0 to resolve the existing drift (`convention`, `engagement`, `readme`, `deck`, `generated`, `session-prompt` already in use)."
  - "`/consulting/templates/` is renamed to `/consulting/methodologies/templates/` in Phase 10.0 to free the `template` catalog kind from collision with prose proposal/SOW/retro templates."
  - "Brand binaries (`logo-*.svg`, `*.potx`, `fonts/*.ttf`) are exempt from the `.meta.yaml` sidecar convention; the brand's `brand.md` manifests its siblings. Exception is documented in `/conventions/frontmatter.md`."
  - "Brand is a small curated catalog: firm brand + co-branded variants + unbranded/clean. Selected at export time or defaulted on the client record."
  - "Bundle composition uses **per-template generators** (each template declares `generator_kind`/`generator_slug`); bundles do not override generators except via explicit `generator_overrides` at export-request time."
  - "Slug-based soft-FKs are paired with **bucket-isolated indexer registration** so `brand_slug`/`bundle_slug`/`template_slug` resolve unambiguously."
---

# Company Edition — fork-and-pivot to a Finance Transformation practice platform

## Context

The team is forking the open-source `autoclaude` repository into a private, company-owned product that serves a Finance Transformation consulting practice. The goal is to consolidate every Claude AI tool, skill, plugin, methodology, and deliverable template the practice uses into one command center — and to make that center an **interactive marketplace** where consultants don't just browse assets, they compose client-branded deliverables on demand.

Today, the autoclaude codebase already gives us most of the skeleton we need: a polymorphic markdown catalog, a Scout ingestion pipeline, an LLM reviewer agent for triage, a SQLite-backed persistent index, a write-back API, an audit log, and a Next.js operator UI. What it does not give us — and what this plan adds — is **multi-client tenancy** (one shared instance, many client contexts), **brand-aware templates** (PPTX/DOCX/PDF deliverables rendered against a per-client brand on demand), **business-process taxonomy** (so a consultant can ask "what helps me with requirements generation?"), **annotated notes with audit semantics**, and a **marketplace UX** that makes capability composition the primary action rather than a side effect of browsing.

Codebase constraints verified by a fresh survey of the current state:

- Catalog is markdown-first; assets are polymorphic with a closed `kind:` enum (`agent`, `skill`, `plugin`, `mcp`, `prompt`, `repo`, `article`, `person`, `org`).
- Persistent index lives in `web/apps/api/db/models.py` (SQLAlchemy) with tables `asset`, `index_meta`, `audit_event`, `proposal`. Alembic migrations: `web/migrations/versions/0001_initial.py` and `0002_writes.py`.
- Web UI scaffold shipping in Phase 8.3 / 8.3b — API at `web/apps/api/`, Next.js 15 at `web/apps/web/`. `Sidebar.tsx` is hardcoded with 8 sections.
- Reviewer agent (Phase 9.0) writes `proposal` rows that the UI triages via `POST /proposals/{id}/accept|reject`.
- Write pipeline at `web/apps/api/writes/{fs,git,editor,triage,audit}.py` already handles file edits + git commits + audit log.
- Engagement frontmatter already carries `client:` as a string, but no `Client` entity or `/clients/` directory exists yet.

## Strategic recommendations (beyond what was asked)

These shape the plan — each is justified inline below.

1. **`Client` is a DB entity, not a catalog kind.** Catalog assets carry mandatory `source.*` / `discovered.*` provenance blocks (`/catalog/_schema/asset.schema.md`); clients have no discovery trail. Forcing them through the markdown shape buys us nothing and loses structured fields (sensitivity tier, contacts, MSA dates).
2. **Brand, Template, and Bundle ARE catalog kinds.** They are reusable artifacts with provenance, status, versioning, tags — a perfect fit for the existing polymorphic asset model. We extend the `kind:` enum rather than build a parallel system.
3. **Bundle = the deliverable unit.** Consultants don't ship "a skill"; they ship a status report. A bundle composes one or more templates + a content generator + a brand (resolved per client at export time) + client notes. This is the marketplace's primary atomic action.
4. **Process-first taxonomy.** Add `business_process` as a controlled vocabulary alongside the existing free-form `tags:` (e.g. `record-to-report`, `order-to-cash`, `requirements-gen`). The marketplace's landing page is process-shaped, not kind-shaped.
5. **Notes are append-only and DB-backed.** Notes are high-frequency, structured, often sensitive (client-confidential), and need audit semantics — the wrong fit for git-tracked markdown.
6. **Finance ontology as a first-class artifact.** Build `/domain/finance-transformation/` with a glossary and process map (R2R, O2C, P2P, FP&A, close). Agents read this as context so they speak finance, not generic consulting.
7. **`Storage` abstraction now, S3 implementation later.** A named interface at `web/apps/api/exports/storage.py` with one concrete `LocalStorage` today, ready to swap for `S3Storage` in Phase 11. Cheapest possible AWS seam.
8. **Provenance manifest on every export.** Every generated deliverable carries an embedded manifest naming the exact bundle / template / brand / generator versions and git SHA that produced it. Audit-grade reproducibility for finance work.
9. **Cost tracking is informational, not a gate.** `ExportJob.cost_usd` is accumulated and displayed in export history so operators can see generator spend over time. No hard budget caps or approval gates — this is an internal tool and that overhead isn't warranted.
10. ~~Sensitivity tier~~ — dropped. This is an internal delivery tool; no per-client access controls, sensitivity tiers, or approval workflows are needed.

## Architecture

### Top-level entities (new)

```
Client (DB)
  ├─ brand_slug → Brand (catalog asset, kind=brand)
  ├─ engagements (existing /consulting/engagements/, frontmatter.client = this.slug)
  └─ notes (DB, append-only)

Brand (catalog, kind=brand)
  Lives at /brands/<slug>/brand.md with binary siblings (logos, fonts, PPTX masters)

Template (catalog, kind=template)
  Lives at /catalog/templates/<slug>.md with binary file under /catalog/templates/files/

Bundle (catalog, kind=bundle)
  Lives at /catalog/bundles/<slug>.md

ExportJob (DB, transient)
  Records: bundle + client + brand + generator + git SHA + artifact paths + manifest

BusinessProcess (DB, seeded)
  Controlled vocabulary: order-to-cash, record-to-report, procure-to-pay,
  hire-to-retire, plan-to-perform, acquire-to-retire (extensible via PR)
```

### Directory layout (deltas from autoclaude)

```
/clients/                       NEW — operator-facing client list (READMEs only)
  /<client-slug>/
    README.md                   non-authoritative summary (data source is DB)
    context/
      context.md                long-form engagement context
/brands/                        NEW — brand assets
  /<client-slug>/
    brand.md                    catalog asset (kind=brand)
    *.png, *.svg, *.potx, *.dotx, fonts/*.ttf
/catalog/templates/             NEW — document templates
  <slug>.md                     catalog asset (kind=template)
  files/<slug>.pptx + .meta.yaml   binary + sidecar (per /conventions/frontmatter.md)
/catalog/bundles/               NEW — bundle definitions
  <slug>.md                     catalog asset (kind=bundle)
/domain/                        NEW — finance-transformation ontology
  /finance-transformation/
    glossary.md, process-map.md
    /processes/r2r.md, o2c.md, p2p.md, fp-and-a.md, close.md
/conventions/                   EXISTING — add brand.md, template.md, bundle.md, business-processes.md
/web/                           EXISTING — extends per phase plan below
```

### New catalog kinds (frontmatter schemas)

**Brand** — `/brands/<client-slug>/brand.md`:

```yaml
name: acme-co-brand
kind: brand
title: "Acme Co — brand"
client: acme-co                  # FK to Client.slug
primary_color: "#0B5FFF"
secondary_color: "#1F2937"
accent_color: "#FBBF24"
heading_font: "Inter"
body_font: "Source Sans Pro"
logo_full: "logo-full.png"       # sibling, validated via writes/fs.safe_path
logo_mono: "logo-mono.svg"
pptx_master: "acme.potx"
docx_master: "acme.dotx"
fonts: ["fonts/Inter-Regular.ttf", "fonts/Inter-Bold.ttf"]
voice:
  tone: confident-but-warm
  taboo: [synergy, leverage]
  preferred: [use, deploy, implement]   # alternatives surfaced to the generator
status: active
```

**Template** — `/catalog/templates/<slug>.md`:

```yaml
name: finance-current-state-deck
kind: template
output_format: pptx              # pptx | docx | xlsx
template_file: "files/finance-current-state.pptx"
placeholders: [client_name, assessment_date, executive_summary, process_map]
generator_kind: skill
generator_slug: finance-current-state-assessor
business_processes: [record-to-report, order-to-cash]
status: active
```

**Bundle** — `/catalog/bundles/<slug>.md`:

```yaml
name: finance-quick-assessment-bundle
kind: bundle
templates: [finance-current-state-deck, finance-roadmap-doc]
placeholder_resolution: template   # locked: each template uses its own generator
business_processes: [order-to-cash]
estimated_duration_minutes: 15
status: active
```

Note: bundles **do not** name a generator. Each listed template owns its own `generator_kind`/`generator_slug`. Conflicting outputs across templates (same placeholder name with different values) are a validation error at bundle save time. The `generator_overrides` field on the export request remains the per-run escape hatch.

**Brand binary exception.** Brand asset binaries (`logo-*.svg`, `*.potx`, `*.dotx`, `fonts/*.ttf` under `/brands/<slug>/`) are explicitly exempt from the `.meta.yaml` sidecar requirement in `/conventions/frontmatter.md`. The `brand.md` itself is the manifest for its siblings — every binary referenced from brand frontmatter is treated as a covered companion. This exception is documented in `frontmatter.md` in Phase **10.0** (the convention edit must precede the `brand` kind landing in 10.1, otherwise 10.1 trips schema validation).

**`kind:` enum split.** Today's `/conventions/kinds.md` declares a closed enum of 9 values, but the live repo already uses `convention`, `engagement`, `readme`, `deck`, `generated`, `session-prompt`. Phase 10.0 splits this into:

- `catalog_kind` (closed): `agent | skill | plugin | mcp | prompt | repo | article | person | org | brand | template | bundle` — enforced for `/catalog/` + `/brands/`.
- `document_kind` (open): `readme | convention | engagement | deck | generated | session-prompt | plan` — open for everything else.

Validation in 10.4 enforces this split. Without it, the existing repo fails schema validation the moment we tighten the loop.

### SQLAlchemy models (additions to `web/apps/api/db/models.py`)

Brand / Template / Bundle stay in the existing `Asset` table — `Asset.kind` is `String(64)`, so new kinds flow through naturally with no schema change. Only entities that don't fit the markdown shape get new tables.

```python
class Client(Base):
    __tablename__ = "client"
    slug = Column(String(128), primary_key=True)
    name = Column(String(256), nullable=False)
    industry = Column(String(128), nullable=True)
    brand_slug = Column(String(128), nullable=True)            # soft FK → asset.slug WHERE bucket='brand'; default brand at export
    engagement_context = Column(Text, nullable=True)           # free-text context injected into generator prompts
    created_at = Column(Float, nullable=False)
    updated_at = Column(Float, nullable=False)

class Note(Base):
    __tablename__ = "note"
    id = Column(String(36), primary_key=True)         # per-revision PK
    note_id = Column(String(36), nullable=False)      # stable across revisions
    revision = Column(Integer, nullable=False, default=1)
    is_current = Column(Boolean, nullable=False, default=True)
    client_slug = Column(String(128), nullable=True)  # null = asset-only note
    asset_slug = Column(String(128), nullable=True)   # null = client-level note; one of these two must be set
    category = Column(String(64), nullable=False)     # finding|risk|comment|tip|warning|usage
    body = Column(Text, nullable=False)
    tags = Column(JSON, default=list)
    created_at = Column(Float, nullable=False)
    __table_args__ = (
        Index("ix_note_client_slug", "client_slug"),
        Index("ix_note_asset_slug", "asset_slug"),
        Index("uq_note_current", "note_id", unique=True, sqlite_where=text("is_current = 1"),
              postgresql_where=text("is_current = true")),
    )

class BusinessProcess(Base):
    __tablename__ = "business_process"
    slug = Column(String(64), primary_key=True)
    name = Column(String(128), nullable=False)
    parent_slug = Column(String(64), nullable=True)
    description = Column(Text, nullable=True)

class ExportJob(Base):
    __tablename__ = "export_job"
    id = Column(String(36), primary_key=True)
    created_at = Column(Float, nullable=False)
    completed_at = Column(Float, nullable=True)
    bundle_slug = Column(String(128), nullable=False)
    client_slug = Column(String(128), nullable=True)       # optional — set when exporting for a specific client
    engagement_slug = Column(String(128), nullable=True)   # optional — for per-engagement filtering
    brand_slug = Column(String(128), nullable=False)
    requested_formats = Column(JSON, nullable=False)
    status = Column(String(16), nullable=False)            # pending|running|complete|failed
    steps = Column(JSON, nullable=False, default=list)     # [{name, status, started_at, completed_at, error}]
    cost_usd = Column(Float, nullable=False, default=0.0)  # accumulated generator spend (informational)
    audit_id = Column(String(36), nullable=True)
    artifacts = Column(JSON, nullable=True)
    manifest = Column(JSON, nullable=True)
    error = Column(JSON, nullable=True)

class UserPreference(Base):
    __tablename__ = "user_preference"
    user_id = Column(String(128), primary_key=True)        # "default" until auth lands
    key = Column(String(64), primary_key=True)             # "sidebar", "theme", etc.
    value = Column(JSON, nullable=False)
    updated_at = Column(Float, nullable=False)
```

**FK strategy:** cross-references between catalog assets and DB entities use **slug-only soft FKs** (no hard FK constraints) because the indexer is eventually-consistent and slugs are stable. App-side validation enforces existence on writes.

**Slug-collision guardrail:** the existing `_find_record` at `web/apps/api/writes/writes.py:39-52` does first-wins on `(bucket, slug)`. The `brand`, `template`, and `bundle` catalog kinds each get **their own buckets** in `indexer.py:classify_bucket` (Phase 10.1 / 10.2b), so `brand_slug='acme-co-brand'` resolves only against `bucket='brand'` rows and cannot collide with a stray `readme` or queue candidate.

**Rename guardrail** — scoped to columns the DB indexes directly: `Client.brand_slug`, `ExportJob.bundle_slug`, `ExportJob.client_slug`, `ExportJob.engagement_slug`, and `Note.asset_slug`. On rename of any asset referenced by these columns, the writes API rejects with `409 referenced-by` unless `?cascade=true` is passed — in which case the API rewrites every referencing row inside the same audit envelope.

**Out of scope for the guardrail (intentional):** slug references that live inside markdown frontmatter (e.g. `brand.md::client`, `dataset.md::client`, `template.md::generator_slug`) and template-slug references inside the `ExportJob.manifest` JSON blob. The rename UI displays a warning citing the affected count from a frontmatter + JSON-containment scan, and operators are expected not to rename assets whose slugs have shipped externally. A fuller cross-frontmatter integrity tool is deferred to 11.x.

**Note revisioning:** `id` is the per-revision PK; `note_id` is the stable identity. On `PUT /notes/{id}`, the API:

1. Sets `is_current=false` on the existing row (no overwrite of `body`).
2. Inserts a new row with the same `note_id`, `revision+1`, `is_current=true`.
3. The partial unique index on `(note_id) WHERE is_current` guarantees exactly one current row per note.

This pattern keeps "current note" queries trivial (`WHERE is_current = true`) and makes history queries cheap (`ORDER BY revision`).

**Per-step export status:** `ExportJob.steps` is a JSON array of `{name, status, started_at, completed_at, error?}` entries written progressively as the pipeline advances (`resolve`, `stage`, `render`, `compose`, `convert`, `persist`, `manifest`, `commit`, `finalize`). The UI renders a step meter; retries can resume from the last failed step.

### Alembic migration — `web/migrations/versions/0003_company_edition.py`

```
revision = "0003"; down_revision = "0002"

upgrade():
  create_table client          (+ ix_client_brand_slug, ix_client_sensitivity_tier)
  create_table note            (+ ix_note_client_slug, ix_note_asset_slug, ix_note_category,
                                  partial unique uq_note_current ON (note_id) WHERE is_current)
  create_table business_process
    op.bulk_insert seed: order-to-cash, record-to-report, procure-to-pay, hire-to-retire,
                         plan-to-perform, acquire-to-retire,
                         requirements-gen, user-story-gen, estimation,
                         status-reporting, change-mgmt
  create_table export_job      (+ ix on client / status / approval_status / created_at)
  create_table user_preference

downgrade(): drop in reverse order, indexes first.
```

No changes to the `asset` table — new `kind:` values are admitted because the column is `String(64)`. Partial unique index uses SQLAlchemy's `sqlite_where` / `postgresql_where` so the migration is portable to RDS Postgres in Phase 11 without rewrite.

### API endpoints (new routers under `web/apps/api/routers/`)

Pattern: thin filters over `Asset` for brands / templates / bundles (mirror `engagements.py`); real CRUD for clients / notes / exports.

```
GET    /clients                            list (filter q)
POST   /clients                            create (DB row + optional /clients/<slug>/README.md scaffold)
GET    /clients/{slug}                     detail + linked brand summary + recent notes
PUT    /clients/{slug}                     update
GET    /clients/{slug}/notes
POST   /clients/{slug}/notes

GET    /notes/{id} / PUT                   append-only (PUT creates new revision row)
GET    /notes/by-stable-id/{note_id}/history   revision history

GET    /brands                             list assets WHERE bucket='brand'
GET    /brands/{slug}                      detail + resolved binary paths
GET    /brands/{slug}/asset/{file}         stream binary companion

GET    /templates                          list (filter output_format, business_process)
GET    /templates/{slug}                   detail incl. placeholder list

GET    /bundles                            list
GET    /bundles/{slug}                     detail with templates resolved

POST   /export/bundle/{slug}               kick off export
GET    /export/jobs/{id}                   poll status + steps[] + manifest
GET    /export/jobs/{id}/artifact/{fmt}    stream download
POST   /export/jobs/{id}/retry             resume from last failed step

GET    /processes                          controlled vocabulary
GET    /processes/{slug}/assets            all assets tagged with this process

GET    /config/sidebar                     user's sidebar config
PUT    /config/sidebar                     update sidebar config

POST   /ingest                             drag/drop ingest (multipart + frontmatter JSON)
                                           — lands in /scout/queue/, triggers reviewer agent
POST   /ingest/dataset                     CSV/XLSX upload — lands as `kind: dataset` asset
                                           with schema introspection (Phase 10.7b)
```

Note: `POST /catalog` is **not** added — the catalog router stays read-only. Ingestion writes to the queue and is triaged through the existing reviewer/proposal flow (`writes.py:92` `POST /queue/{slug}/triage`).

### Export pipeline (the deliverable engine)

New module `web/apps/api/exports/pipeline.py` plus the `Storage` interface at `web/apps/api/exports/storage.py` (one concrete `LocalStorage` now; future `S3Storage` swap).

Call sequence for `POST /export/bundle/{slug}` with `{ client_slug?, brand_slug, formats, context?, commit_to_engagement?, engagement_slug?, generator_overrides? }`. Each numbered step writes a `{name, status, ...}` entry into `ExportJob.steps` as it begins and updates it on completion/failure.

1. **resolve** — `_find_record` (writes.py:39) for bundle / brand / templates; optional DB lookup for Client (if `client_slug` provided) to pull `engagement_context` and default `brand_slug`. 404 on any missing asset.
2. **stage** — open audit + job. `begin_audit(action="export-bundle", ...)` (audit.py:51); insert `ExportJob` row, `status=pending`. `Storage.workspace(job_id)` returns a fresh tmpdir. Copy brand binary assets via `writes/fs.safe_path`.
3. **render** — per template, invoke its declared generator (`template.generator_kind`/`generator_slug`, overridden by `generator_overrides`). Generator returns `{placeholder_name: fragment}` plus a `cost_usd` it spent. Accumulate into `ExportJob.cost_usd`. **Validation:** reject as `422 placeholder-conflict` if two templates' generators produce the same placeholder key with non-equal values (defense in depth — bundle save also rejects this).
4. **compose** — per template (this is where chart-generation lives; see below):
   - `pptx` → `python-pptx`, open master, replace `{{placeholders}}`, apply brand colors via theme overrides, emit native chart objects for `chart_spec` placeholders
   - `docx` → `python-docx` with `dotx` master
   - `xlsx` → `openpyxl`
5. **convert** — if requested format ≠ template native, shell `libreoffice --headless --convert-to pdf` (binary path via `settings.libreoffice_bin`). Non-zero exit or zero-byte output surfaces as `502 conversion-failed` on this step only — the native-format artifact from step 4 is still persisted.
6. **persist** — `Storage.put(job_id, format, bytes)`; compute sha256 + size; attach to `ExportJob.artifacts`.
7. **manifest** — capture `raw_hash` from each `AssetRecord` (indexer.py:91) + `git rev-parse HEAD` (via `writes/git.py`) + accumulated `cost_usd`. Store on `ExportJob.manifest` and embed a copy in PPTX/DOCX file properties.
8. **commit** (optional) — if `commit_to_engagement=true`, copy artifacts into `/consulting/engagements/<slug>/deliverables/` with `.meta.yaml` sidecars and commit via `writes/git.py`. Default is `false` — consultants opt in per export.
9. **finalize** — `audit.commit(result=...)`; set `ExportJob.status="complete"`; trigger `index.sync()` if anything landed in the repo.

**Charts in deliverables.** Templates may declare a `chart_spec` placeholder type (e.g. `executive_summary_chart: { kind: chart_spec, type: bar_clustered, data_source: <generator-output-key> }`). The compose step (4) instantiates native `python-pptx`/`python-docx`/`openpyxl` chart objects so downstream consumers can edit the chart in PowerPoint, not just see a flattened image. Chart styling pulls from the brand's color palette.

**Failure modes the API surfaces explicitly (each on a specific step):**

- `422 placeholder-missing` (step render) — generator didn't fill a declared placeholder
- `422 placeholder-conflict` (step render) — two generators wrote the same placeholder with different values
- `409 brand-asset-missing` (step stage) — brand `.md` out of sync with binary siblings
- `502 conversion-failed` (step convert) — LibreOffice non-zero or zero-byte output; native-format artifact retained (partial success)

All follow the existing `with begin_audit` failure pattern in `writes.py:148-176` and write the failure into `ExportJob.steps[i].error` so the UI can render a per-step progress meter.

### Marketplace UX (frontend pivot)

The current frontend is a database browser. The pivot is to a **task-oriented launcher**:

- **`/` (landing)** — "What are you working on today?" with shortcuts:
  - "Generate a deliverable" → pick bundle + client → run export
  - "Start an engagement" → wizard
  - "Find a capability" → process-oriented search
  - "Browse the library" → existing catalog view (still available)
- **`/process/<slug>`** — one page per business_process; shows description, methodology, capabilities, templates, bundles, past usages
- **Asset detail pages** — add a "Use this" panel: try in playground, add to bundle, generate deliverable with this
- **`/composer`** — visual canvas: drag templates + capabilities → save as bundle (Phase 10.5; drag-drop polish later)

### Configurable sidebar

The hardcoded `Sidebar.tsx` becomes data-driven. Sidebar config lives in `user_preference` table keyed by `key="sidebar"`:

```json
{
  "visible": ["dashboard","clients","catalog","bundles","engagements","queue","proposals"],
  "hidden":  ["scout-sources","threads","conventions","plans"],
  "order":   ["dashboard","clients","catalog","bundles","engagements","queue","proposals"]
}
```

Until auth lands, `user_id="default"` and the config is per-instance. Settings page at `/settings/sidebar` with drag-to-reorder + visibility toggles.

### Drag-and-drop ingestion

`POST /ingest` (multipart + frontmatter JSON) is the markdown / plugin / template entry point; `POST /ingest/dataset` is the tabular (CSV/XLSX) entry point added in 10.7b. UI: drop zone on the catalog landing page that routes by detected MIME type. Pipeline:

1. Detect file type (`.md`, `.json` plugin manifest, `.pptx` template, `.csv`/`.xlsx` dataset, etc.)
2. Route to the appropriate extractor (reuse `scout/extractors/` patterns)
3. Land in `/scout/queue/` (markdown/plugin/template) or `/datasets/<slug>/` (tabular) — both create a queue candidate
4. Reviewer agent auto-classifies; operator triages via `/proposals`

The catalog router stays read-only by design; all ingest writes flow through the existing Scout → Queue → Reviewer → Proposal → Catalog pipeline.

### AWS-portability seams (built now, deferred implementation)

| Concern | Seam (Phase 10.x) | Implementation (Phase 11.0) |
|---|---|---|
| File storage | `Storage` interface + `LocalStorage` | `S3Storage` swap |
| Index DB | SQLAlchemy with portable types only | `DATABASE_URL` env → RDS Postgres |
| Auth | `current_user()` returning `"default"` | Cognito SSO behind same dependency |
| Secrets | Read via `os.getenv` from `.env` | AWS Secrets Manager |
| Background jobs | inline asyncio for v1 | SQS + Lambda |
| Logging | structured JSON stdout from day one | CloudWatch ingest |
| Export rendering | LibreOffice CLI locally | Lambda + Gotenberg |

Build the seams. Skip the cloud code until Phase 11.

## Phase plan

Each phase is sized to a focused session and lands a usable increment.

- **10.0 — Fork, rename & schema hygiene (1 day).** Hard-fork into private company repo. Rename Python package + CLI scripts (`autoclaude` → `<hub>`). Drop open-source-only seed content unrelated to finance — keep schema + examples. Update CLAUDE.md header. **Schema hygiene (new):** split `kind:` enum into `catalog_kind` (closed) and `document_kind` (open); rename `/consulting/templates/` → `/consulting/methodologies/templates/`; document brand binary `.meta.yaml` exception in `/conventions/frontmatter.md`. Smoke-test API + web boot. Copy this plan into `/docs/plans/company-edition.md` in the new repo.
- **10.1 — Client record + brand kind (1.5 days).** Migration 0003 (client + business_process + user_preference tables only). `Client` router (lightweight: slug, name, industry, brand_slug, engagement_context). New `catalog_kind: brand` admitted; `brand` bucket added to `indexer.classify_bucket` for slug isolation. `/brands/<slug>/brand.md` examples (firm brand + unbranded variant). Brand router (read-only). Backfill: wire one engagement to point at a `Client` row.
- **10.2a — Export pipeline spike (1 day, non-shippable).** **De-risk before building.** Hardcoded end-to-end: one template (PPTX), one brand (firm colors + logo), one generator output. Validate that (a) `python-pptx` can swap brand colors on a real `.potx` master (known to require XML-level manipulation), and (b) LibreOffice headless converts the result legibly with embedded TTF fonts. Spike must use `-env:UserInstallation=file:///tmp/lo-<uuid>` in the subprocess call (concurrency safety — document this in the findings). Output: spike script at `/web/apps/api/exports/spikes/` + findings doc at `/docs/plans/10-2a-export-spike-findings.md`. **Exit criterion:** branded PPTX → branded PDF round-trip works, or findings doc identifies the blocking gap and names the fallback.
- **10.2b — Templates + bundles + native-format export (3 days).** New catalog kinds `template`, `bundle` (in their own buckets). Routers. `Storage` interface + `LocalStorage`. Pipeline steps 1–4 + 6 + 7 + 9 (`resolve`, `stage`, `render`, `compose`, `persist`, `manifest`, `finalize`). Native format only — no PDF, no charts yet. Provenance manifest. UI: deliverable wizard ("pick bundle → pick client → export").
- **10.2c — PDF, charts & commit (1.5 days).** Pipeline steps 5 (`convert` via LibreOffice) and 8 (`commit` to engagement, opt-in). `chart_spec` placeholder type with native `python-pptx`/`openpyxl` chart objects. `ExportJob.cost_usd` accumulation (informational, displayed in export history). Per-step status meter in the wizard UI.
- **10.3 — Notes (1 day).** `Note` table (already in migration 0003) with `note_id`/`revision`/`is_current` partial unique index. Notes API. UI: notes panel on Client and Asset pages. No access controls — notes are internal-only and visible to all operators.
- **10.4 — Business-process taxonomy + finance ontology + brand voice (2.5 days).** Seed `business_process` rows in 0003. Extend asset frontmatter validation to recognize `business_processes:` and enforce the new `catalog_kind`/`document_kind` split. Backfill existing catalog with tags. Build `/domain/finance-transformation/` content. Update reviewer-agent prompt (Phase 9.0) to classify new tag axes. **Brand voice in generator prompts (new):** the generator dispatcher (`exports/generators.py`) now injects the resolved brand's `voice` block (`tone`, `taboo`, `preferred`) as a system-prompt header for every generator invocation; a generator that emits a `taboo` word is logged and surfaces a warning on the export job (non-blocking; partners decide whether to reject).
- **10.5 — Marketplace UX (2.5 days).** New landing page ("What are you working on today?"). Process pages. "Use this" affordances on asset detail. Composer view (basic list-and-select). Export history panel with download links.
- **10.6 — Configurable sidebar (0.5 day).** `UserPreference` row (already in 0003). `/config/sidebar` endpoints. Settings page with drag-to-reorder.
- **10.7a — Markdown ingestion UI (1.5 days).** `POST /ingest` multipart endpoint. UI drop zone. Route uploads through Scout queue → reviewer agent → proposals UI. Reuse `writes/{editor,git,audit}.py`.
- **10.7b — Tabular ingestion (2 days).** New `catalog_kind: dataset` for CSV/XLSX inputs (client GLs, trial balances, KPI workbooks). `POST /ingest/dataset` introspects schema (column names, types, row count, head rows), stores binary under `/datasets/<slug>/`, generates `dataset.md` frontmatter. Templates can declare a `dataset` placeholder type that pulls structured data into chart_spec inputs. PII redaction hook: optional regex-based mask at ingest time for restricted-tier clients.
- **10.8 — Cloud-readiness pass (2 days).** Storage interface adoption everywhere (eliminate direct file I/O). Structured JSON logging. Dockerfile. All paths via env vars. `current_user()` shim. No actual cloud code. Pre-flight for Phase 11.

**Out of this plan (future):**

- **11.0** — AWS deploy (Cognito, RDS, S3, ECS, CloudFront, Secrets Manager). Separate plan.
- **11.1** — Workflow builder (chained asset invocations). Separate plan.
- **11.2** — Granular RBAC, partner / admin / consultant roles.

## Critical files

### Modify

- `/CLAUDE.md` — update for new product identity, new layout, new kinds
- `/catalog/_schema/asset.schema.md` — admit `brand`, `template`, `bundle` kinds
- `/conventions/frontmatter.md` — document new fields (`business_processes:`, brand fields, template/bundle compositions)
- `/web/apps/api/db/models.py` — add Client, Note, BusinessProcess, ExportJob, UserPreference
- `/web/apps/api/indexer.py` (~line 160) — `classify_bucket` recognizes `brands/`, `catalog/templates/`, `catalog/bundles/`
- `/web/apps/api/main.py` — register new routers
- `/web/apps/web/components/Sidebar.tsx` — data-driven from `/config/sidebar`
- `/web/apps/web/app/page.tsx` (or new `app/(launcher)/page.tsx`) — landing-page rework

### Create

- `/web/migrations/versions/0003_company_edition.py`
- `/web/apps/api/routers/{clients,brands,templates,bundles,notes,exports,processes,config,ingest}.py`
- `/web/apps/api/exports/{pipeline,storage,generators,charts}.py`
- `/web/apps/api/exports/spikes/10_2a_pptx_brand_swap.py` (one-off, archived after 10.2a)
- `/web/apps/web/app/{clients,brands,templates,bundles,process,composer,settings,exports}/...`
- `/conventions/{brand,template,bundle,dataset,business-processes,sensitivity-tiers}.md`
- `/domain/finance-transformation/{glossary,process-map}.md` + `/processes/*.md`
- `/clients/_template/` + `/brands/_template/` skeletons
- `/datasets/_template/` skeleton (10.7b)
- `/docs/plans/10-2a-export-spike-findings.md` (output of 10.2a)

## Existing utilities to reuse (do not reinvent)

| Need | Reuse |
|---|---|
| Frontmatter parsing | `scout._util.parse_frontmatter` |
| Slug + URL canonicalization | `scout._util.slugify`, `canonical_github_url` |
| Safe path resolution | `web/apps/api/writes/fs.py::safe_path` |
| Git commits from API writes | `web/apps/api/writes/git.py` |
| Frontmatter assembly for writes | `web/apps/api/writes/editor.py` |
| Audit log lifecycle | `web/apps/api/writes/audit.py::begin_audit` |
| Reviewer agent for new assets | `scout/reviewer/` (entire module; just extend prompt for new tag axes) |
| Read-side query helpers | `web/apps/api/db/query.py` |
| Sync indexer ↔ DB | `web/apps/api/db/sync.py` |
| Existing engagement router as pattern | `web/apps/api/routers/engagements.py` |

## Operator questions (answered 2026-06-19)

1. **License posture on forked content.** ✅ Keep all content under the original open-source license. No relicensing; no assets dropped.
2. **New repo identity.** ✅ Deferred — will be set up on company domain later. Current private repo is the working instance.
3. **Auth-deferral risk tolerance.** ✅ Acceptable. API runs unauthenticated (`user_id="default"`) on operator's local machine through Phase 10. No basic-auth wrapper needed.
4. **Client ↔ Brand cardinality.** ✅ 1:1 — one structured package per client. `Client.brand_slug` model is correct.
5. **PII / data-residency commitments.** ✅ No special commitments. Client brand is used only for created documentation; no cross-border data constraints.

## Open decisions (all resolved 2026-06-19)

1. **Working name.** ✅ **Forge.**
2. **PDF conversion engine.** ✅ **LibreOffice headless** for Phase 10.x; **Gotenberg** (ECS sidecar) for Phase 11 cloud. Key implementation constraint: every `subprocess.run` call must pass `-env:UserInstallation=file:///tmp/lo-<uuid>` to isolate the per-conversion LibreOffice profile directory — concurrent exports will collide without it. Embed fonts in the PPTX master and install any brand TTF/OTF at image build time (`/usr/local/share/fonts/`). The 10.2a spike validates fidelity on a real branded `.potx`; if chart rendering is unacceptable, Aspose is the commercial fallback (not Gotenberg — same fidelity as LibreOffice under the hood). Supported deliverable types catalogued in `/conventions/deliverable-types.md`.
3. **Reviewer-agent budget defaults.** ✅ Keep at $5/day (no change).
4. **`commit_to_engagement` default.** ✅ Opt-in (`false` by default) — already locked above.

## Out of scope (explicit)

- Multi-instance / true SaaS multi-tenancy
- External client-facing portal (clients do not log in — this is an internal tool)
- Sensitivity tiers, approval workflows, per-client cost budgets (internal tool; no tenancy semantics)
- PII redaction on ingest
- Time tracking / billing / CRM integration
- Real-time collaboration (we generate and export, not co-author)
- Fine-tuning models on internal assets
- Granular RBAC
- Phase 11 cloud deploy (separate plan)

## Verification

End-to-end smoke after each phase:

- **After 10.0:** `uv run pytest && uv run autoclaude-api` boots under new package name; `( cd web/apps/web && npm run dev )` renders the dashboard. Schema validation accepts both new `catalog_kind` and existing `document_kind` values; `/consulting/methodologies/templates/proposal.md` indexes cleanly.
- **After 10.1:** `POST /clients` creates Acme; `GET /clients/acme-co` returns it with `brand_summary`. `/brands/firm/brand.md` indexed in bucket `brand` and visible at `GET /brands/firm`. An export request that omits `brand_slug` falls back to `Client.brand_slug`.
- **After 10.2a (spike):** `/web/apps/api/exports/spikes/10_2a_pptx_brand_swap.py` runs end-to-end on a real `.potx` → branded `.pptx` → branded `.pdf`. Findings doc names any technique gaps that change 10.2b/c scope.
- **After 10.2b:** `POST /export/bundle/finance-quick-assessment-bundle?client=acme-co` returns a job; polling `GET /export/jobs/{id}` shows `steps[]` advancing through `resolve|stage|render|compose|persist|manifest|finalize`; `status=complete` with a downloadable `.pptx` whose colors match Acme brand and whose embedded properties include the manifest JSON (bundle/template/brand/generator versions + git SHA).
- **After 10.2c:** Same export with `formats: [pptx, pdf]` returns both artifacts; a `chart_spec` placeholder renders as a native, editable PowerPoint chart (not an image). `ExportJob.cost_usd` is populated and visible in export history.
- **After 10.3:** Notes appear on a Client page and on an Asset page; `PUT /notes/{id}` creates a revision row, the old row stays with `is_current=false`.
- **After 10.4:** Browsing `/process/record-to-report` lists every asset tagged for R2R; reviewer agent on a fresh candidate assigns a `business_processes:` tag. A frontmatter with `kind: brand` in `/scout/queue/` is rejected by validation (queue uses document_kind only).
- **After 10.5:** Landing page loads as the task launcher, not the database browser. Generating an export completes immediately and is available for download from the export history panel.
- **After 10.6:** Hiding a sidebar section in `/settings/sidebar` persists across page reloads.
- **After 10.7a:** Drag-dropping a `.md` skill file onto the catalog page creates a queue candidate at `/scout/queue/` and an immediate reviewer-agent proposal at `/proposals`.
- **After 10.7b:** Drag-dropping `gl-q2-2026.xlsx` creates a `dataset` asset with schema introspection in frontmatter (columns, types, row count). A bundle template can reference `dataset: gl-q2-2026` in a `chart_spec` placeholder and the resulting PPTX contains a chart sourced from real values. PII redaction hook is not implemented (internal tool; not needed).
- **After 10.8:** `docker build .` succeeds; `docker run -e DATABASE_URL=sqlite:///...` boots the API against a swapped storage root; no hardcoded paths remain. Logs are structured JSON.

A full PR-by-PR test plan accompanies each phase commit; the convention `/conventions/testing.md` already specifies layout (unit vs integration, fixtures, markers).
