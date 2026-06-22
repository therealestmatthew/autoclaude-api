# Static export profiles

Reusable filter configs for `ft-autoclaude-export-static`. Each YAML in this directory is a named profile that selects a different slice of the catalog for distribution.

## Usage

```sh
uv run ft-autoclaude-export-static --config profiles/client-share.yaml --out dist/client-share
uv run ft-autoclaude-export-static --config profiles/internal.yaml      --out dist/internal
uv run ft-autoclaude-export-static --config profiles/anaplan-build.yaml --out dist/anaplan-build
```

See [command-center/runbooks/static-export.md](../command-center/runbooks/static-export.md) for the full filter shape.

## Profiles

| Profile | Audience | What ships |
|---------|----------|------------|
| [client-share.yaml](client-share.yaml) | External client stakeholders | Adopted + reviewed, action-kinds + templates, no plans, no drafts |
| [internal.yaml](internal.yaml) | Internal team | Everything including drafts, plans, conventions |
| [anaplan-build.yaml](anaplan-build.yaml) | A specific workstream during the Build phase | Vetted items tagged for `build`, `integration`, or `testing` |

## Adding a new profile

1. Copy the closest existing profile in this directory
2. Rename it (`profiles/<slug>.yaml`)
3. Edit the filter rules — see the inline comments
4. Add a row to the table above
5. Test with `--no-build -v` first to see what would ship before running the full Next.js build
