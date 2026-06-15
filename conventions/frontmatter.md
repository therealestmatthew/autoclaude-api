# Frontmatter

YAML frontmatter is the structured layer over our markdown. Every catalog asset, scout queue candidate, and engagement folder root has it.

## Catalog asset — canonical shape

The authoritative spec lives in `/catalog/_schema/asset.schema.md`. Summary of required vs optional below.

### Required

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

### Optional but encouraged

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
client: acme-co
status: prospecting | active | paused | completed
started_on: 2026-06-14
ended_on:                       # set when completed
sow_url:                        # link to signed SOW
---
```

## Dates

- Always ISO `YYYY-MM-DD`.
- When recording a date a user said in natural language ("Thursday", "next week"), convert to absolute before writing.
