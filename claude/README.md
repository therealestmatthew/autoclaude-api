# /claude/

The agentic-delivery IP we own and actively use. Distinct from `/catalog/`, which is what we *collect* — `/claude/` is what we *build and run*.

## Catalog vs. /claude/

| If…                                                              | It lives in…                  |
| ---------------------------------------------------------------- | ----------------------------- |
| We found it externally and decided to remember it                | `/catalog/<slug>.md`          |
| We use it actively (ours or adapted from external)               | `/claude/<area>/<slug>/`      |
| It's external, *and* we use it actively                          | Both. Catalog entry's `status: adopted`. |

The catalog records origin and judgment. `/claude/` is the working artifact.

## Subdirs

- [agents/](agents/) — Claude (Code) agent definitions.
- [skills/](skills/) — Claude Code skills.
- [plugins/](plugins/) — Claude Code plugins (bundles).
- [mcp/](mcp/) — MCP servers and configs.
- [prompts/](prompts/) — reusable prompts and templates.
- [playbooks/](playbooks/) — how to *use* the above effectively in delivery work.

## Conventions

- Each artifact gets its own subdirectory: `/claude/agents/<slug>/`, `/claude/skills/<slug>/`, etc. The subdirectory holds the artifact files plus a `README.md` explaining purpose, when to use it, and known limitations.
- The slug matches the catalog slug when adopted from an external asset.
- Internal originals get a fresh slug.
- Every artifact's README links back to its catalog entry (if any) with the slug.
