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

### Child slugs (extracted from a parent)

When an extractor surfaces a child asset out of a parent (e.g. an `agent` file inside a scouted GitHub `repo`), the child's slug is **scoped under the parent**:

```
<parent-slug>--<child-name>
```

- Double-dash (`--`) is the scope separator. It is the only place `--` appears in a well-formed slug, so it is visually unambiguous against the kebab-case dashes inside each segment.
- `<child-name>` is the kebab-cased file or directory name that uniquely identifies the child within its parent (filename without `.md` for agents/prompts; directory name for skills/plugins; `mcp-<server-name>` for MCP server entries).
- Like every other slug, the result is globally unique across `/catalog/`. If a parent legitimately contains two children that would collide (e.g. `agents/foo.md` and `.claude/agents/foo.md`), the extractor emits the first and logs a warning; we do not auto-disambiguate.
- The scoping is a property of the *slug*, not of the on-disk path: child files still live flat in `/catalog/<slug>.md`. The graph link back to the parent lives in `relations.parent`.

**Example.** A repo scouted as `anthropic-claude-cookbooks` containing `.claude/agents/code-reviewer.md` and `skills/test-runner/SKILL.md` yields children `anthropic-claude-cookbooks--code-reviewer` and `anthropic-claude-cookbooks--test-runner`.

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
