# /conventions/

The rulebook. Every other directory's README points back here for the *how* of writing in this repo.

## Documents

- [naming.md](naming.md) — slugs, file names, directory names.
- [frontmatter.md](frontmatter.md) — YAML frontmatter spec used across catalog, scout queue, and engagements.
- [kinds.md](kinds.md) — the closed enum of asset `kind:` values and what each means.
- [merge-rules.md](merge-rules.md) — how to decide merge vs new vs discard when reviewing a scout candidate.
- [contribution.md](contribution.md) — the writing flow: where things start, how they get reviewed, where they end up.
- [testing.md](testing.md) — how we write tests: unit vs integration directories, fixtures, markers, speed budget.
- [security.md](security.md) — threat model + defenses for ingesting untrusted content (sanitization, URL safety, bounded GET, defusedxml, repo-clone sandboxing).

## Principles

1. **Markdown + frontmatter beats a database** until it demonstrably doesn't. The repo is the DB.
2. **Provenance is non-negotiable.** Every catalog asset must say where it came from and when we found it.
3. **Slugs are identity.** Once an asset has a slug, that slug doesn't change. Rename = breakage.
4. **One shape, one place.** Polymorphic assets, flat collection. We add typed folders or new schemas only when the pain is real and named.
5. **Human-in-the-loop by default.** Automation proposes; humans (or, later, an explicit reviewer agent) decide.
