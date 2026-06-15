# /catalog/_examples/

Worked examples of the asset schema, one per kind we want to illustrate. **These are documentation, not real catalog entries.** They live in `_examples/` so they don't pollute the catalog and are obvious by location.

## Files

- [example-agent.md](example-agent.md) — an `agent` extracted from a parent repo.
- [example-skill.md](example-skill.md) — a `skill` standing on its own.
- [example-repo.md](example-repo.md) — a `repo`, parent of the example agent and skill.
- [example-article.md](example-article.md) — an `article`.

These show the parent/child pattern: a single scouted repo can produce multiple child assets. The repo carries the source URL once; children carry `parent: <repo-slug>` and their own specifics.

## When to update these

- Whenever the schema changes (see `/catalog/_schema/README.md`).
- Whenever a convention they demonstrate changes.
- Never with content drift from real assets — these aren't trying to track the world, they're trying to teach the shape.
