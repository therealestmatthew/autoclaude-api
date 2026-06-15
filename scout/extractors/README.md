# /scout/extractors/

Per-source parsers. Each extractor is responsible for one source `type` (matching the `type:` field in `/scout/sources/*.yaml`).

## Extractor contract

```python
# Conceptual; not yet implemented.

class Extractor(Protocol):
    type: str                                  # matches source.type

    def fetch(self, source: SourceConfig, state: State) -> Iterable[Candidate]:
        """Yield candidates newer than state.cursor. Update cursor as we go."""
```

## Extractors planned

| Type           | Source                                  | Status                            |
| -------------- | --------------------------------------- | --------------------------------- |
| `awesome-list` | Markdown lists at known URLs            | **Phase 2 — `awesome_list.py`**   |
| `hackernews`   | Algolia search API                      | **Phase 3 — `hackernews.py`**     |
| `lobsters`     | Per-tag RSS                             | **Phase 3 — `lobsters.py`**       |
| `reddit`       | `/r/<sub>/new.json`                     | **Phase 3 — `reddit.py`**         |
| `github-repo`  | `git clone <url>` + tree walk           | Phase 4 (per-clone container)     |
| `x`            | Twitter/X API (decision pending)        | Phase 5                           |

`github-repo` is special — it's not a *discovery* extractor; it's invoked when any other extractor surfaces a `github.com/*` URL. It clones the repo and proposes child assets (agents, skills, plugins, MCPs, prompts) from the tree.

## Security baseline (Phase 3.0)

Every extractor here uses the helpers in `scout/_security.py` — no exceptions:

- **`safe_get_bytes(client, url, …)`** for every HTTP call: URL is validated
  against an allow/deny list pre-request, the final URL is re-checked after
  redirects, and the body stream is capped at 10MiB by default. Raw
  `client.get()` is not allowed in extractor code.
- **`sanitize_text(s, max_length=…)`** on every free-form string that ends up
  in a `Candidate` (title, author, excerpt). Strips control / bidi /
  zero-width / surrogate / private-use codepoints, NFC-normalizes, collapses
  whitespace, length-caps.
- **XML parsing** (currently lobsters) goes through `defusedxml`. No bare
  `xml.etree.ElementTree`.

The rules live in `/conventions/security.md`; the tests prove they fire in
`tests/unit/test_security.py` and in the per-extractor unit tests.

## Why one extractor per source type

Sources differ in fundamental ways — auth, pagination, rate limits, content shape. A "universal" extractor would either be a thick framework or a shallow one full of `if source == ...`. Cheaper to keep them separate and let them share a `Candidate` data shape.
