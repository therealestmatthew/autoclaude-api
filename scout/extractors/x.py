"""X / Twitter extractor — deferred stub.

Phase 5 resolved the auth question with the **defer** path (option c in the
plan). X API access is paid as of 2026, third-party mirrors are operationally
fragile, and the HN / Reddit echo channel already surfaces the high-signal
X content that crosses a threshold worth tracking. So this extractor exists
only to keep the registry shape consistent.

Re-enabling later (whether by paid API access or by a stabilized mirror)
means: flip `scout/sources/x-handles.yaml` to `enabled: true`, fill in this
class's `fetch` method, drop the stub raise, and update the plan with the
new locked decision. The session-prompt skeleton in
/docs/plans/phase-5-x-twitter.md still applies to the active extractor work.
"""

from __future__ import annotations

from collections.abc import Iterator

from ..agent.types import Candidate, SourceState, XSource


class XExtractorDeferred(NotImplementedError):
    """Raised when the X extractor is invoked while the source is enabled but
    no auth path has been wired. Carries a pointer to the plan."""


class XExtractor:
    type = "x"

    def fetch(
        self, source: XSource, state: SourceState, run_id: str
    ) -> Iterator[Candidate]:
        # `enabled: false` in scout/sources/x-handles.yaml means the runner
        # short-circuits before ever calling us. If someone flips the flag
        # without wiring auth, fail loudly rather than silently dropping
        # candidates.
        raise XExtractorDeferred(
            "X / Twitter extractor is deferred (Phase 5 locked decision). "
            "See /docs/plans/phase-5-x-twitter.md to re-open."
        )
        yield  # pragma: no cover  (here to type as a generator)
