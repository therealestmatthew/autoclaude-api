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

| Type           | Source                                  | Status                          |
| -------------- | --------------------------------------- | ------------------------------- |
| `awesome-list` | Markdown lists at known URLs            | **Phase 2 — `awesome_list.py`** |
| `hackernews`   | Algolia search API                      | Phase 3                         |
| `lobsters`     | Per-tag RSS                             | Phase 3                         |
| `reddit`       | `/r/<sub>/new.json`                     | Phase 3                         |
| `github-repo`  | `git clone <url>` + tree walk           | Phase 4                         |
| `x`            | Twitter/X API (decision pending)        | Phase 5                         |

`github-repo` is special — it's not a *discovery* extractor; it's invoked when any other extractor surfaces a `github.com/*` URL. It clones the repo and proposes child assets (agents, skills, plugins, MCPs, prompts) from the tree.

## Why one extractor per source type

Sources differ in fundamental ways — auth, pagination, rate limits, content shape. A "universal" extractor would either be a thick framework or a shallow one full of `if source == ...`. Cheaper to keep them separate and let them share a `Candidate` data shape.
