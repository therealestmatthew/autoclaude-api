# Asset kinds

The `kind:` field is a closed enum. Adding a new kind is a deliberate decision — propose it in a PR with at least two example assets that would need it, and update this file in the same change.

## Current kinds

| Kind      | What it is                                                                                  | Typical `parent` | Example                              |
| --------- | ------------------------------------------------------------------------------------------- | ---------------- | ------------------------------------ |
| `agent`   | A specialized Claude (or other LLM) agent definition. Has a role, instructions, tools.      | a `repo`         | `claude-code-reviewer-agent`         |
| `skill`   | A Claude Code skill — packaged capability invoked by name.                                  | a `repo`         | `verify-skill`                       |
| `plugin`  | A Claude Code plugin (bundle of skills/agents/commands).                                    | a `repo`         | `ultrareview-plugin`                 |
| `mcp`     | An MCP server (config + capabilities).                                                      | a `repo`         | `supabase-mcp`                       |
| `prompt`  | A reusable prompt or prompt template not packaged as a skill/agent.                         | a `repo` or none | `code-review-prompt`                 |
| `repo`    | A whole code repository worth tracking. Often the parent of multiple extracted children.    | none             | `anthropics-claude-cookbooks`        |
| `article` | A blog post, doc page, paper, or video transcript.                                          | none             | `anthropic-effective-agents-essay`   |
| `person`  | An individual whose output we want to track.                                                | none             | `simon-willison`                     |
| `org`     | An organization (Anthropic, a vendor, a community) whose output we want to track.           | none             | `anthropic`                          |

## Picking the right kind

- If it's *a thing inside a repo* (an agent file, a skill folder, an MCP config), use the specific kind and set `relations.parent` to the repo slug.
- If it's the repo itself and we don't yet know what's inside, use `repo`. Extraction (Phase 4) will create child assets later.
- If it's a written piece (essay, doc, video), use `article`.
- If it's a feed source (a person or org we follow for future signal, not a specific artifact), use `person` or `org`.

## What is not a kind

- "Idea", "todo", "note" — those don't belong in `/catalog/`. Use the relevant subsystem's own folder.
- "Library" or "tool" generic — if it's not Claude-adjacent enough to fit the kinds above, it probably doesn't belong here at all.
