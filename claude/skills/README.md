# /claude/skills/

Claude Code skills we use. One subdirectory per skill, structured to match the Claude Code skill packaging conventions so the directory can be symlinked or copied into a Claude Code skills path directly.

## Layout per skill

```
<slug>/
  SKILL.md        the skill definition (frontmatter + body, per Claude Code conventions)
  README.md       our notes: purpose, when to use, links back to catalog if external
  <assets>        whatever else the skill needs (scripts, examples, references)
```

## Origin

- **Adopted from external:** catalog entry `status: adopted`, README starts with `Catalog: [<slug>](../../../catalog/<slug>.md)`.
- **Original:** no catalog entry needed.

## Note for Claude Code

When `/claude/skills/` becomes large enough, consider symlinking the whole directory under the Claude Code skills path (`~/.claude/skills/` or project-local) so these are available wherever Claude Code runs.
