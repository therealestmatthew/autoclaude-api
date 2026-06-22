# Content Management Runbook

Covers four operations: configuring UI tabs, manually adding/removing catalog assets, reviewing the scout queue via the web UI, and manually adding items to the queue.

---

## 1. Configuring which tabs appear in the sidebar

Edit `/web/apps/web/nav.config.json`. Each entry has a `key` and an `enabled` flag. Tabs appear in the order listed.

```json
{
  "tabs": [
    { "key": "dashboard",   "enabled": true  },
    { "key": "skills",      "enabled": true  },
    { "key": "timelines",   "enabled": true  },
    { "key": "engagements", "enabled": true  },
    { "key": "catalog",     "enabled": true  },
    { "key": "queue",       "enabled": true  },
    { "key": "proposals",   "enabled": true  },
    { "key": "threads",     "enabled": true  },
    { "key": "conventions", "enabled": false },
    { "key": "plans",       "enabled": false }
  ]
}
```

**To hide a tab:** set `"enabled": false`.  
**To reorder tabs:** move the object to a different position in the array.  
**To add a new tab:** it must first exist as a page route under `web/apps/web/app/` and be registered in `TAB_REGISTRY` inside `Sidebar.tsx` — see that file for the pattern.

The change takes effect on the next `npm run dev` restart (dev) or build deploy (prod).

---

## 2. Manually adding catalog assets

A catalog asset is a markdown file with YAML frontmatter at `/catalog/<slug>.md`. The slug must be globally unique, kebab-case, and match the filename.

### Step-by-step

1. **Choose a slug.** Kebab-case, descriptive, globally unique. Check for conflicts:
   ```sh
   ls catalog/ | grep <candidate-slug>
   ```

2. **Create the file** at `/catalog/<slug>.md` using this template:

   ```markdown
   ---
   name: <slug>
   kind: <kind>
   title: "Human-Readable Title"
   status: reviewed

   quality: <1-5>
   tags: [tag-one, tag-two]

   source:
     type: manual          # github | x | hn | reddit | awesome-list | article | manual
     url: https://...
     authors: []
     license: ""

   discovered:
     via: manual
     on: <YYYY-MM-DD>

   relations:
     parent:
     related: []
     supersedes: []

   fingerprint: ""
   created_at: <YYYY-MM-DD>
   updated_at: <YYYY-MM-DD>
   ---

   # <slug>

   Why we kept this, how we use it, what's good about it, what to watch out for.
   ```

3. **Fill in `kind`.** Valid values for `/catalog/` assets:

   | Kind | What it is |
   |------|------------|
   | `agent` | An agentic workflow or Claude Code agent |
   | `skill` | A Claude Code skill (slash command) |
   | `plugin` | A standalone plugin (not MCP) |
   | `mcp` | An MCP server |
   | `prompt` | A standalone prompt or prompt library |
   | `repo` | A GitHub repository (often parent of agents/skills) |
   | `article` | Blog post, paper, guide |
   | `org` | A company/team/project |
   | `person` | An individual author or practitioner |
   | `brand` | A client brand reference |
   | `template` | A deliverable template (PPTX/DOCX/XLSX) |
   | `bundle` | A bundle composition (template + generator + brand) |
   | `dataset` | A structured dataset |

4. **If the asset is adopted into active use**, also:
   - Set `status: adopted`
   - Copy the working artifact into `/claude/<area>/` (agents, skills, plugins, mcp, prompts, playbooks)
   - Add a note in the body about any local modifications

5. **Commit the file.** The web UI refreshes its index on the next API sync:
   ```sh
   uv run ft-autoclaude-index sync
   ```

### Parent/child assets

A `repo` asset can have many `agent` or `skill` children. Set the child's `relations.parent` to the repo's slug:

```yaml
relations:
  parent: some-repo-slug
```

---

## 3. Manually removing catalog assets

Catalog files are kept forever for audit history — **do not delete them**. Instead, archive them.

1. Open `/catalog/<slug>.md`.
2. Change `status: reviewed` (or `adopted`) to `status: archived`.
3. Update `updated_at` to today's date.
4. If the asset is being superseded by another, fill `relations.supersedes` on the replacement and note why in the body.

If the asset lives in `/claude/` as an adopted working copy, remove or rename that copy separately — the catalog entry is the record of judgment, not the working file.

After editing, sync the index:
```sh
uv run ft-autoclaude-index sync
```

---

## 4. Reviewing queued items via the web UI

The scout pipeline writes candidate files to `/scout/queue/`. The Queue tab in the web UI (http://localhost:3000/queue) is the triage interface.

### Workflow

1. **Open the Queue tab.** Cards show title, kind, source, and tags.

2. **Click a card** to open the triage detail view.

3. **Read the candidate.** The full frontmatter and body are shown on the left panel.

4. **Choose an action** in the right-hand TriagePanel:

   | Action | When to use |
   |--------|-------------|
   | **Keep** | Asset is new and worth keeping. Optionally override the target slug before submitting. A live slug-collision check flags if the slug already exists in the catalog. |
   | **Merge** | Asset duplicates something already in `/catalog/`. Type to search the catalog autocomplete, then select the canonical asset to merge into. |
   | **Discard** | Asset is noise, low-quality, or out of scope. Add a note for the audit trail (required). |

5. **Submit.** The backend writes the triage result, moves or deletes the queue file, updates the catalog, and records an audit entry. The page auto-refreshes.

### LLM-generated proposals

The reviewer agent (Phase 9.0) generates triage proposals for queue candidates automatically. These appear in the **Proposals** tab rather than Queue. The workflow is the same — accept or reject each proposal, optionally editing the target slug or notes.

---

## 5. Manually adding items to the queue

The queue at `/scout/queue/` accepts markdown files in the same frontmatter format as catalog assets but with `status: draft`. The scout pipeline and triage UI consume anything placed there.

### Option A — create a file directly

Create `/scout/queue/<slug>.md` with this minimal shape:

```markdown
---
name: <slug>
kind: <kind>
title: "Title of the thing"
status: draft
tags: []

source:
  type: manual
  url: https://...
  authors: []
  license: ""

discovered:
  via: manual
  on: <YYYY-MM-DD>

created_at: <YYYY-MM-DD>
updated_at: <YYYY-MM-DD>
---

Notes on why this looks interesting. Not yet reviewed.
```

The item will appear in the Queue tab immediately (the index refreshes on next sync or API restart).

### Option B — run the scout pipeline

To pull new signals from configured sources:

```sh
uv run scout run                       # all enabled sources
uv run scout run -s awesome-lists      # one specific source
uv run scout run -v                    # verbose output
```

Candidates land in `/scout/queue/` and appear in the Queue tab.

### Option C — run the reviewer agent (LLM triage)

If the API server is running and `ANTHROPIC_API_KEY` is set, generate automatic proposals for pending queue items:

```sh
uv run scout review --dry-run          # preview decisions, no writes
uv run scout review --limit 25         # generate up to 25 proposals
```

Proposals appear in the **Proposals** tab for operator approval.

---

## Quick reference

| Task | Command / File |
|------|---------------|
| Show/hide a sidebar tab | `/web/apps/web/nav.config.json` |
| Add a catalog asset | Create `/catalog/<slug>.md` |
| Archive a catalog asset | Set `status: archived` in frontmatter |
| Browse the queue | http://localhost:3000/queue |
| Add to queue manually | Create `/scout/queue/<slug>.md` |
| Run scout | `uv run scout run` |
| Sync the index | `uv run ft-autoclaude-index sync` |
| Run LLM reviewer | `uv run scout review --limit 25` |
