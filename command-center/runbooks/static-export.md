# Static Export — packaging the catalog for the team

Build a self-contained, browser-friendly bundle of the catalog that anyone can open in a browser, host on S3/SharePoint/Cloudflare Pages, or share as a ZIP. No Docker, no Python, no Node.js on the recipient's machine.

## What's included

- The full catalog browser UI (skills, catalog, dashboard, conventions, plans pages)
- The "By Function" view organized by Anaplan delivery phase
- Search, kind/status filtering (all client-side)
- Per-asset detail pages with rendered markdown
- A ⬇ Download .md button on every catalog/skill detail page

## What's excluded

Write/operator features that need the API: queue triage, proposals inbox, edit pages, thread logs, engagements, timelines. The tabs are hidden in the static build; if a recipient navigates to those URLs directly, they get a "not part of the static export" placeholder.

## Build it

```sh
uv run ft-autoclaude-export-static
```

Output lands at `dist/catalog-static/` by default. Override with `--out <path>`.

Other useful flags:
- `--config <path>` — use a different filter config (default: `export.config.yaml`)
- `--no-build` — only refresh the data bundle in `web/apps/web/public/data/`, skip the Next.js build
- `-v` / `--verbose` — show timing and intermediate counts

## Choosing what to include

The filter rules live in `/export.config.yaml`. Defaults: ship `adopted` + `reviewed` catalog items, keep conventions, drop plans, no kind/function/tag restriction.

### Filter shape

```yaml
include:
  status: [adopted, reviewed]     # required statuses (OR within the list)
  kind: []                        # required kinds (empty = all)
  delivery_function: []           # required Anaplan delivery phases (empty = all)
  tags: []                        # required tags (empty = all)

exclude_slugs: []                 # hard deny — wins over everything
include_slugs: []                 # hard allow — bypasses include rules
include_conventions: true         # ship /conventions/
include_plans: false              # ship /docs/plans/
```

An item ships when:
1. Its `slug` is in `include_slugs` *(unconditional allow)*, **OR**
2. It matches every active rule in `include:` (empty list = unrestricted on that dimension)

And in all cases:
- Items in `exclude_slugs` are dropped, no matter what

### Maintaining multiple profiles

Three ready-to-use profiles live in `/profiles/` — see [`profiles/README.md`](../../profiles/README.md) for the catalog.

```sh
# External-stakeholder build (adopted + reviewed only, action-kinds + templates)
uv run ft-autoclaude-export-static --config profiles/client-share.yaml --out dist/client-share

# Internal-team build (everything, including drafts and plans)
uv run ft-autoclaude-export-static --config profiles/internal.yaml --out dist/internal

# Workstream-specific build (Anaplan Build phase)
uv run ft-autoclaude-export-static --config profiles/anaplan-build.yaml --out dist/anaplan-build
```

Common profile patterns:

| Profile | Rules |
|---------|-------|
| **Adopted-only** (vetted, actively used) | `status: [adopted]` |
| **Anaplan-build phase** | `status: [adopted, reviewed]`, `delivery_function: [build, integration, testing]` |
| **Action tools only** (no articles/orgs) | `kind: [agent, skill, plugin, mcp, prompt]` |
| **Opt-in via tag** | tag every shareable asset with `client-safe`, then `tags: [client-safe]` |

The active filter is recorded in the bundle's `data/manifest.json` so you can confirm what shipped.

The pipeline:
1. Walks the repo with the same indexer the API uses
2. Writes `catalog.json`, per-asset detail JSONs, raw `.md` files, and a manifest into `web/apps/web/public/data/`
3. Runs `next build` with `NEXT_PUBLIC_STATIC_MODE=true` and `output: 'export'`
4. Copies the static `out/` directory to the target

## Share it

The output directory is fully self-contained. Three ways to distribute:

### Option 1 — Zip and email
```sh
cd dist && zip -r catalog-static.zip catalog-static
```
~3 MB. Recipient unzips and opens `index.html` in a browser.

### Option 2 — Host on any static file server
```sh
# Local quick share
python -m http.server -d dist/catalog-static 8080
```
Then send the URL.

For permanent hosting:
- **Cloudflare Pages** — drag the folder into the dashboard, get a `*.pages.dev` URL
- **AWS S3 + CloudFront** — sync the folder to a bucket with static website hosting
- **GitHub Pages** — commit `dist/catalog-static/` to a `gh-pages` branch
- **SharePoint / corporate file share** — most internal portals will serve static HTML directly

### Option 3 — Open directly from filesystem
Modern browsers can open `index.html` from a `file://` URL. Some features (search debounce, fonts) may behave better when served from a real HTTP server.

## Updating the bundle

The bundle is a snapshot. To distribute updated catalog content:
1. Make edits to the markdown files in `/catalog/`, `/conventions/`, `/docs/plans/`
2. Re-run `uv run ft-autoclaude-export-static`
3. Redistribute the new `dist/catalog-static/`

No version tracking inside the bundle — the snapshot timestamp lives in `data/manifest.json` if you need to confirm freshness.

## Troubleshooting

**Build fails on `await searchParams`** — A new page uses `await searchParams` in a server component. Refactor to a server-wrapper-loads-all-data + client-component-filters-via-`useSearchParams()` pattern (see `SkillsBrowser.tsx` and `CatalogBrowser.tsx` for the template).

**Build fails with "Module not found: 'fs'"** — A client component imports from a path that ultimately loads `static-data.ts`. Either move the import server-side, or extend the `fs: false` webpack fallback in `next.config.mjs`.

**Detail page is missing for a slug you expect** — Check `web/apps/web/public/data/slug-index.json`. The slug must be in the index and in the `catalog` bucket. If it's missing, the source `.md` file may have a different `bucket` classification — see `web/apps/api/indexer.py::classify_bucket`.

**The download button 404s** — Raw `.md` files are written to `data/raw/<slug>.md`. Make sure the slug matches the frontmatter `name:` field exactly. If `name:` is missing, the indexer falls back to the filename stem.
