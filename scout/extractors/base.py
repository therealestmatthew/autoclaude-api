"""Extractor protocol — what every per-source extractor must provide."""

from __future__ import annotations

from collections.abc import Iterator
from typing import Any, Protocol

from ..agent.types import Candidate, SourceState


class Extractor(Protocol):
    """One extractor per source `type`.

    Stateless: the runner owns persistence. The extractor receives the parsed
    source config and a mutable SourceState it may update (e.g. recording URLs
    it has emitted). It yields Candidate objects.
    """

    type: str

    def fetch(
        self,
        source: Any,
        state: SourceState,
        run_id: str,
    ) -> Iterator[Candidate]:
        ...
