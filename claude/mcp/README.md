# /claude/mcp/

MCP (Model Context Protocol) servers and their configs. One subdirectory per server.

## Layout per MCP

```
<slug>/
  README.md             purpose, capabilities exposed, auth requirements
  server/               source code or vendor-pinned reference
  config.example.json   sanitized config snippet (no secrets)
```

## Conventions

- Secrets never live in this directory. Config examples use placeholders (`<YOUR_TOKEN>`).
- If the MCP server is third-party, the README links to the upstream and the relevant catalog entry.
- If it's our own, the source lives here directly.
