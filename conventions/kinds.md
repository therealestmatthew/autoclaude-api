# Asset kinds

Every markdown document in this repo has a `kind:` in its frontmatter. As of Phase 10.0, `kind:` is split into two distinct enums based on where the document lives.

## Two enums, two policies

| Enum | Scope | Policy | Add a value via |
|---|---|---|---|
| `catalog_kind` | `/catalog/` and `/brands/` | **Closed.** A new value is a deliberate decision. | PR with at least two example assets that would need it, and an update to this file. |
| `document_kind` | Everywhere else (`/conventions/`, `/docs/plans/`, `/command-center/`, READMEs, etc.) | **Open.** Descriptive label for documents that aren't catalog assets. | Just use the value. Document common ones here so vocabulary doesn't sprawl. |

The split exists because catalog assets carry mandatory `source.*` / `discovered.*` provenance and are FK-referenced by DB tables (brands → clients, bundles → templates). They need a closed, audited vocabulary. Conventions, plans, runbooks, and READMEs don't — they're documents about the system rather than artifacts inside it.

## catalog_kind (closed)

Used for files under `/catalog/` and `/brands/`. The indexer's `bucket` classification expects exactly these.

| Kind         | What it is                                                                                  | Typical `parent` | Example                              |
| ------------ | ------------------------------------------------------------------------------------------- | ---------------- | ------------------------------------ |
| `agent`      | A specialized Claude (or other LLM) agent definition. Has a role, instructions, tools.      | a `repo`         | `claude-code-reviewer-agent`         |
| `skill`      | A Claude Code skill — packaged capability invoked by name.                                  | a `repo`         | `verify-skill`                       |
| `plugin`     | A Claude Code plugin (bundle of skills/agents/commands).                                    | a `repo`         | `ultrareview-plugin`                 |
| `mcp`        | An MCP server (config + capabilities).                                                      | a `repo`         | `supabase-mcp`                       |
| `prompt`     | A reusable prompt or prompt template not packaged as a skill/agent.                         | a `repo` or none | `code-review-prompt`                 |
| `repo`       | A whole code repository worth tracking. Often the parent of multiple extracted children.    | none             | `anthropics-claude-cookbooks`        |
| `article`    | A blog post, doc page, paper, or video transcript.                                          | none             | `anthropic-effective-agents-essay`   |
| `person`     | An individual whose output we want to track.                                                | none             | `simon-willison`                     |
| `org`        | An organization (Anthropic, a vendor, a community) whose output we want to track.           | none             | `anthropic`                          |
| `brand`      | A client or firm brand identity — colors, fonts, logos, voice, document masters. Lives in `/brands/<slug>/brand.md`. | none | `forge-brand` |
| `template`   | (Phase 10.2+) A deliverable template (PPTX/DOCX/XLSX) with placeholders and a generator.    | none             | `finance-current-state-deck`         |
| `bundle`     | (Phase 10.2+) A composition of templates + business process + business-process tags.        | none             | `finance-quick-assessment-bundle`    |
| `dataset`    | (Phase 10.7b+) A tabular client input (CSV/XLSX) with schema introspection in frontmatter.  | none             | `acme-gl-q2-2026`                    |

The Phase 10.x kinds (`brand`, `template`, `bundle`, `dataset`) are reserved here so the closed enum doesn't have to expand mid-phase. They go live as each phase ships per `/docs/plans/company-edition.md`.

### Picking the right catalog_kind

- If it's *a thing inside a repo* (an agent file, a skill folder, an MCP config), use the specific kind and set `relations.parent` to the repo slug.
- If it's the repo itself and we don't yet know what's inside, use `repo`. The repo extractor (Phase 4) will create child assets later.
- If it's a written piece (essay, doc, video), use `article`.
- If it's a feed source (a person or org we follow for future signal, not a specific artifact), use `person` or `org`.
- If it's a client identity or context — **stop**. Clients are DB entities, not catalog assets. See `/docs/plans/company-edition.md` for the rationale.

## document_kind (open)

Used for everything else. These don't go in `/catalog/` and aren't expected to carry provenance. The list below is **descriptive** — add new values as needed; just document them here when you do.

| Kind             | What it is                                                                            | Where it lives                                    |
| ---------------- | ------------------------------------------------------------------------------------- | ------------------------------------------------- |
| `readme`         | Directory README explaining what belongs in that directory.                           | every dir, conventionally                         |
| `convention`     | A repo-wide rule (this file, frontmatter spec, security policy, etc.).                | `/conventions/`                                   |
| `plan`           | A phase plan or feature plan — design lineage that persists.                          | `/docs/plans/`                                    |
| `session-prompt` | A short prompt that primes a fresh Claude Code session for a specific phase.          | `/docs/plans/session_prompts/`                    |
| `runbook`        | An operator or user procedure that should be followable cold.                         | `/command-center/runbooks/`, `/docs/runbooks/`    |
| `methodology`    | A consulting delivery/discovery/estimation playbook.                                  | `/consulting/methodologies/`                      |
| `engagement`     | The root document for a single client engagement.                                     | `/consulting/engagements/<year>-<slug>/`          |
| `deck`           | A presentation outline or slide notes (not the binary export — those carry sidecars). | various                                           |
| `generated`      | A document produced by an export pipeline; treat as derived, not source of truth.     | various, often in `/consulting/engagements/.../deliverables/` |
| `timeline`       | A customizable date-shaped view (project plan, adoption roadmap, content calendar) with `entries:` in frontmatter. | `/timelines/<slug>.md` |

If you find yourself wanting to add a value that overlaps with an existing one, prefer the existing one. If your value really is distinct, add it here in the same PR.

## Why not just one open enum

We had one enum through Phase 9 and watched it drift — `convention`, `engagement`, `readme`, `deck`, `generated`, `session-prompt` all appeared in the live repo without ever being added to the enum. The closed-enum policy was unenforceable because the surface was too broad.

The two-enum split makes the policy enforceable where it matters (catalog) and lets documents that describe the system carry useful labels without ceremony.

## What is not a kind (in either enum)

- "Idea", "todo", "note" — those don't belong as standalone documents. Notes about catalog assets live in the `note` DB table (Phase 10.3+); ideas/todos belong in a personal scratch file or a `/docs/plans/` plan.
- "Library" or "tool" as a generic catch-all — if it doesn't fit a specific catalog_kind, it probably doesn't belong in `/catalog/` at all.
