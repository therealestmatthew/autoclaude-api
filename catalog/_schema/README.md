# /catalog/_schema/

Canonical schema for catalog assets. The leading `_` keeps it sorted to the top and signals "this is meta, not a real catalog entry."

- [asset.schema.md](asset.schema.md) — full field-by-field spec.

If you change the schema, the same PR must:

1. Update `asset.schema.md`.
2. Update `/conventions/frontmatter.md` summary table.
3. Update each file in `/catalog/_examples/` to demonstrate the change.
4. Note the change in the PR description.

Schema changes are migrations. They cost. Make them deliberately.
