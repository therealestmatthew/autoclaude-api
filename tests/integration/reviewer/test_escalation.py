"""Integration: Sonnet low-confidence triggers Opus escalation."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest

from .conftest import write_queue_item


def _make_response(action: str, confidence: float) -> MagicMock:
    block = MagicMock()
    block.type = "tool_use"
    block.name = "emit_decision"
    block.input = {"action": action, "confidence": confidence, "rationale": "Test."}
    usage = MagicMock()
    usage.input_tokens = 400
    usage.output_tokens = 60
    usage.cache_read_input_tokens = 100
    usage.cache_creation_input_tokens = 0
    response = MagicMock()
    response.content = [block]
    response.usage = usage
    return response


@pytest.mark.integration
def test_escalation_on_low_confidence(reviewer_world):
    """When Sonnet returns confidence < 0.6, runner calls Opus next."""
    queue_dir = reviewer_world["queue"]
    threads_dir = reviewer_world["threads"]
    write_queue_item(queue_dir, "hard-case")

    sonnet_response = _make_response("keep", confidence=0.45)  # below threshold
    opus_response = _make_response("discard", confidence=0.88)

    mock_client = MagicMock()
    mock_client.messages.create.side_effect = [sonnet_response, opus_response]

    from scout.reviewer.runner import run_review

    with patch("scout.reviewer.runner._post_proposal", return_value={"id": "px"}):
        with patch("scout.reviewer.runner._get_existing_proposals", return_value=[]):
            with patch("anthropic.Anthropic", return_value=mock_client):
                with patch.dict("os.environ", {"ANTHROPIC_API_KEY": "test-key"}):
                    stats = run_review(
                        dry_run=False,
                        queue_dir=queue_dir,
                        threads_dir=threads_dir,
                    )

    assert stats["escalations"] == 1
    assert stats["action_counts"]["discard"] == 1  # took Opus decision
    # Two API calls were made (Sonnet + Opus)
    assert mock_client.messages.create.call_count == 2


@pytest.mark.integration
def test_no_escalation_when_force_model_set(reviewer_world):
    """--model opus skips escalation logic."""
    queue_dir = reviewer_world["queue"]
    write_queue_item(queue_dir, "easy-case")

    # Even with low confidence, force_model prevents escalation attempt
    opus_response = _make_response("discard", confidence=0.3)
    mock_client = MagicMock()
    mock_client.messages.create.return_value = opus_response

    from scout.reviewer.runner import run_review

    with patch("anthropic.Anthropic", return_value=mock_client):
        with patch.dict("os.environ", {"ANTHROPIC_API_KEY": "test-key"}):
            stats = run_review(
                dry_run=True,
                queue_dir=queue_dir,
                force_model="claude-opus-4-7",
            )

    assert stats["escalations"] == 0
    assert mock_client.messages.create.call_count == 1
