# Testing

How we write tests in this repo. Short, prescriptive.

## Two kinds, two directories

- **Unit** — `tests/unit/`. Fast. No network. No broad filesystem. One module
  under test per file. Anything that's a pure function, a parser, a formatter, a
  data-shape transformation lives here.
- **Integration** — `tests/integration/`. Multiple modules cooperate. Real
  filesystem under `tmp_path`. Still **no network** — use `httpx.MockTransport`.
  The orchestrator (`runner.run_once`), the future reviewer agent, the
  Phase 4 repo extractor, all get an integration test here.

Network IO is banned in both. Determinism matters more than realism — a flaky
test gets skipped, then ignored, then we ship the regression it was meant to catch.

## Commands

```sh
uv run pytest                          # everything
uv run pytest tests/unit               # unit only
uv run pytest tests/integration        # integration only
uv run pytest -m "not integration"     # equivalent to unit-only via marker
uv run pytest -k slugify               # filter by name substring
uv run pytest --collect-only -q        # show what would run, without running
uv run pytest -x --pdb                 # stop at first failure and drop to debugger
```

`uv run` evaluates against the project venv each time; no manual activate.

## Fixtures

- `tests/conftest.py` — shared across the whole suite (e.g. `sample_candidate`,
  `make_mock_httpx_client`).
- `tests/integration/conftest.py` — integration-specific (e.g. `scout_world`,
  which sets up an isolated catalog/queue/state/threads world and patches the
  runner's module-level paths).
- Per-file local helpers — fine if a single test file uses them.

Put a fixture at the *lowest* scope that satisfies its callers. Only promote it
to a shared conftest when a second test wants it. Premature shared fixtures
become dumping grounds.

## Markers

Declared in `pyproject.toml`:

- `integration` — auto-applied to every test in `tests/integration/` via that
  directory's `conftest.py`. You don't decorate by hand.

To add a new marker (e.g. `slow`, `network`), declare it in
`pyproject.toml` *and* describe its meaning here.

## Naming

- File: `test_<module>.py` matching the module under test for unit;
  `test_<workflow>.py` for integration.
- Function: `test_<what_is_asserted>` — describe the assertion, not the action.
  `test_canonical_url_dedup_catches_subtree_links` beats `test_runner_works`.
- Class: optional grouping (e.g. `class TestSlugify`). Use sparingly — pytest
  doesn't need them, and they add an indentation level.

## When to write what

| Kind        | Trigger                                                                                |
| ----------- | -------------------------------------------------------------------------------------- |
| Unit        | Every pure function or method we author. Always.                                       |
| Unit        | Every parser / formatter / serializer. The *contract* matters more than the code.      |
| Integration | Every orchestration loop (runner, reviewer, extractors that touch multiple subsystems).|
| Integration | When two modules' contracts need to be exercised together.                             |
| Neither     | Glue code with no logic — re-exports, trivial wiring, dataclass field assignment.      |

## What never to test

- Third-party library schemas. Trust pydantic, trust httpx, trust pyyaml.
- The Python interpreter.
- Boilerplate that has no decision in it.

A test that asserts only that a library does what its documentation says it does
is noise. Delete it.

## Speed budget

- Unit suite: **under one second** wall-clock locally.
- Integration suite: **under five seconds** wall-clock locally.

When the suite slows down, find the slow test and split or rework it. Slow
suites get skipped, then untrustworthy, then deleted.

## Security tests for extractors

Every new extractor (anything that fetches untrusted content from the public
internet) **must** ship with at least one adversarial unit test that
demonstrates the security helpers from `scout/_security.py` are wired
correctly. This is a merge gate, not a nice-to-have — the helpers are only
load-bearing if the test would fail when they're removed.

Pick at least one of the following per extractor:

- **Oversized response** — fixture exceeds `safe_get_bytes`'s `max_bytes`
  cap; assert `ResponseTooLargeError` is raised, OR is caught by the
  extractor and recorded in `state.stats[...errors]`.
- **Hidden Unicode in a title** — fixture title contains a bidirectional
  override (`U+202E`), zero-width joiner (`U+200B`), or null byte; assert the
  yielded `Candidate.title` no longer contains it.
- **Redirect to a private IP** — `httpx.MockTransport` returns a 3xx to
  `http://127.0.0.1/` (or `10.0.0.0/8`); assert `UnsafeURLError` is raised
  pre- or post-redirect, OR caught and recorded in `state.stats[...errors]`.

A single test that exercises one case is enough — the goal is to lock in
that the helpers run on real input, not to re-test the helpers (their own
coverage lives in `tests/unit/test_security.py`).

## Static fixtures

`tests/fixtures/` holds reusable static input — markdown samples, sample YAML
configs, broken catalog assets used by parser tests. Don't put one-off data
there. See `tests/fixtures/README.md` for the convention.

## Writing the test before the change

For anything beyond a trivial fix, write the failing test first. Two reasons:

1. A test you can write before the code locks the *contract* you're aiming at.
   A test you write after the code locks in the *implementation* you happened to
   land on, which is rarely what you actually meant.
2. The diff makes the change reviewable: the test describes the intent, the
   implementation satisfies it.

This is doctrine, not religion — skip it for one-line bug fixes where the test
is obvious. For everything else: red, then green.

## When tests fail

If you're updating a test to make it pass, ask: did the contract change on
purpose? Updating a test because the *contract* changed is fine. Updating a test
to silence a *regression* is how regressions ship.
