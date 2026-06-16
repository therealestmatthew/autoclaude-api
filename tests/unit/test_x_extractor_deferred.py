"""The X extractor is a deferred stub (Phase 5 locked decision).

Goal of this test: lock in the contract — if someone flips
`scout/sources/x-handles.yaml` to `enabled: true` without first wiring an
auth path, the extractor must fail loudly rather than silently dropping
candidates or pretending the source returned nothing.
"""

from __future__ import annotations

import pytest

from scout.agent.types import MatchSpec, SourceState, XSource
from scout.extractors.x import XExtractor, XExtractorDeferred


def test_fetch_raises_when_invoked() -> None:
    source = XSource(
        name="x-handles",
        type="x",
        enabled=True,
        handles=["AnthropicAI"],
        match=MatchSpec(any_of=["claude code"]),
    )
    state = SourceState(source="x-handles")
    extractor = XExtractor()
    with pytest.raises(XExtractorDeferred):
        # Generators don't run until you pull from them.
        next(extractor.fetch(source, state, "test-run"))


def test_registry_round_trip() -> None:
    from scout.agent.runner import EXTRACTOR_REGISTRY, SOURCE_MODELS

    assert "x" in EXTRACTOR_REGISTRY, "registry must keep an x slot — the YAML still references it"
    assert SOURCE_MODELS["x"] is XSource
