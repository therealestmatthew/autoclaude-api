# tests/fixtures/

Static sample data shared across tests. Use this directory when:

- A test needs a representative input that the test isn't responsible for
  constructing — a realistic awesome-list markdown sample, a malformed catalog
  asset, a full source YAML, etc.
- More than one test wants the same input.

Don't use it when:

- The input is small enough to inline. A 3-line YAML literal in the test body
  beats a fixture file every time.
- The input is specific to one test.

## Loading a fixture

```python
from pathlib import Path

FIXTURES = Path(__file__).resolve().parents[1] / "fixtures"   # from tests/unit/<file>

def test_something():
    sample = (FIXTURES / "awesome-list-sample.md").read_text()
    ...
```

For session-wide reuse, build a fixture in `tests/conftest.py` that reads the
file once and returns its text.

## Naming

Fixture files take a slug name and the natural extension: `awesome-list-sample.md`,
`broken-frontmatter.md`, `hackernews-results.json`. Group by topic, not by the
test that uses them.
