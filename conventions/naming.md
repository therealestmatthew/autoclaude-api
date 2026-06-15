# Naming

## Slugs

A slug is an asset's permanent identity. Treat it like a primary key.

- Lowercase ASCII, words separated by `-`.
- Globally unique across all kinds in `/catalog/`.
- Stable: once assigned, never rename. If an asset's meaning changes substantially, create a new one and use `supersedes:`.
- Descriptive without being a sentence. 2–5 words usually.

**Good:** `claude-code-best-practices`, `anthropic-skills-repo`, `simon-willison`, `awesome-claude-code`.
**Bad:** `the-best-claude-code-guide-from-anthropic-blog`, `repo1`, `claude_code_BP`, `notes-from-tuesday`.

### How to derive a slug

1. Strip the source's marketing prefix (`The Ultimate`, `A Guide to`, etc.).
2. Reduce to the noun phrase that identifies the thing.
3. Kebab-case it.
4. Check `/catalog/` for collisions; if one exists, disambiguate with the author/org (`code-review-anthropic` vs `code-review-cursor`), not a number suffix.

## File names

- **Catalog assets:** `<slug>.md`. No kind prefix, no subfolders by kind.
- **Conventions / READMEs / docs:** lowercase kebab-case `.md`.
- **Source configs:** `<source>.yaml` in `/scout/sources/`.
- **Scout queue items:** `<scouted-at>-<slug-or-source>-<short-hash>.md`. The date prefix gives natural sort and dedup hints.
- **Engagements:** `/consulting/engagements/<yyyy>-<client-slug>/` — year groups, client identifies.

## Directories

- Lowercase kebab-case.
- Leading `_` prefix means "meta / template / not real content" (e.g., `_schema/`, `_examples/`, `_template/`). These are intentionally sorted to the top and not treated as regular assets.
- One README per directory. It states purpose, what belongs there, and what doesn't.
