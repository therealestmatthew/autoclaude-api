# /claude/agents/

Claude agent definitions we use in delivery work. One subdirectory per agent.

## Layout per agent

```
<slug>/
  README.md       purpose, when to invoke, known limitations
  agent.md        the agent definition (system prompt, tools, model)
  examples/       optional: sample inputs/outputs
```

The agent definition format follows the conventions of whichever runtime hosts it (Claude Code subagent, Claude Agent SDK, etc.). The `README.md` explains the *intent* and the *fit* — when to reach for this agent rather than another.

## Linking back to /catalog/

If the agent originated from a scouted asset, its README starts with:

```markdown
Catalog: [<slug>](../../../catalog/<slug>.md)
```

If it's original IP, no catalog link.
