# FT-AutoClaude

**An Agentic Solutions Marketplace for Finance Transformation consulting.** A private hard-fork of the open-source `autoclaude` command-and-control center, retargeted for a Finance Transformation consulting practice.

This repo consolidates the assets, conventions, and operations that turn solo delivery into a leveraged, repeatable practice. Two halves live here:

- **/consulting/** — the consulting business: methodologies, templates, positioning, engagements.
- **/claude/** — agentic delivery IP: agents, skills, plugins, MCP servers, prompts, playbooks.

Three cross-cutting subsystems tie them together:

- **/catalog/** — the master database of everything we've collected or built (agents, skills, plugins, repos, prompts, articles, people, orgs). One polymorphic asset shape, flat collection, indexed by frontmatter.
- **/scout/** — the discovery pipeline. Watches X, HN, Reddit, Lobsters, and curated awesome-lists for signal, queues candidates, and (once built) clones referenced GitHub repos to extract artifacts into the catalog.
- **/command-center/** — orchestration and observability: agentic thread logs, token-burn reports, operator runbooks.

## How information flows

```
discovery sources  →  /scout/queue/  →  human review  →  /catalog/
(X, HN, Reddit,                       (merge / new /
 awesome-lists)                        discard)
                                                            ↓
                                              promoted to /claude/* when adopted
                                              as a working part of our toolkit
```

## Status

Phase 3 shipped — three social/list sources (HackerNews, Lobste.rs, Reddit) feeding the catalog queue, all wired through a Phase 3.0 security baseline (`scout/_security.py` + `/conventions/security.md`). Catalog seeded with eight real assets from the installed Claude Code stack. See `CLAUDE.md` for setup and commands, `/conventions/` for how to write to the repo, and `/catalog/_schema/` for the asset shape.

## For Claude Code

`CLAUDE.md` at the repo root is the operating brief for future Claude Code instances working in this repo. Read it first.
