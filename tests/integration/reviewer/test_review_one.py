"""Integration: one candidate → one proposal POST."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest

from .conftest import write_queue_item


@pytest.mark.integration
def test_review_one_candidate_dry_run(reviewer_world, make_tool_use_response):
    queue_dir = reviewer_world["queue"]
    write_queue_item(queue_dir, "claude-cookbooks")

    mock_response = make_tool_use_response("keep", confidence=0.9)
    mock_client = MagicMock()
    mock_client.messages.create.return_value = mock_response

    from scout.reviewer.runner import run_review

    with patch("scout.reviewer.runner._post_proposal") as mock_post:
        with patch("anthropic.Anthropic", return_value=mock_client):
            with patch.dict("os.environ", {"ANTHROPIC_API_KEY": "test-key"}):
                stats = run_review(
                    dry_run=True,
                    queue_dir=queue_dir,
                    limit=1,
                )

    assert stats["processed"] == 1
    assert stats["action_counts"]["keep"] == 1
    assert stats["proposed"] == 0  # dry run: no POST
    mock_post.assert_not_called()


@pytest.mark.integration
def test_review_one_candidate_live(reviewer_world, make_tool_use_response):
    queue_dir = reviewer_world["queue"]
    threads_dir = reviewer_world["threads"]
    write_queue_item(queue_dir, "claude-cookbooks")

    mock_response = make_tool_use_response("discard", confidence=0.95)
    mock_client = MagicMock()
    mock_client.messages.create.return_value = mock_response

    mock_proposal = {"id": "abc123", "status": "pending"}

    from scout.reviewer.runner import run_review

    with patch("scout.reviewer.runner._post_proposal", return_value=mock_proposal) as mock_post:
        with patch("scout.reviewer.runner._get_existing_proposals", return_value=[]):
            with patch("anthropic.Anthropic", return_value=mock_client):
                with patch.dict("os.environ", {"ANTHROPIC_API_KEY": "test-key"}):
                    stats = run_review(
                        dry_run=False,
                        queue_dir=queue_dir,
                        threads_dir=threads_dir,
                        api_url="http://localhost:8000",
                    )

    assert stats["processed"] == 1
    assert stats["proposed"] == 1
    mock_post.assert_called_once()
    payload = mock_post.call_args[0][1]
    assert payload["action_kind"] == "discard"
    assert payload["source"] == "reviewer-agent"
    assert payload["target_bucket"] == "queue"


@pytest.mark.integration
def test_review_records_token_usage(reviewer_world, make_tool_use_response):
    queue_dir = reviewer_world["queue"]
    threads_dir = reviewer_world["threads"]
    write_queue_item(queue_dir, "test-item")

    mock_response = make_tool_use_response("keep", confidence=0.88)
    mock_client = MagicMock()
    mock_client.messages.create.return_value = mock_response

    from scout.reviewer.runner import run_review

    with patch("scout.reviewer.runner._post_proposal", return_value={"id": "x1"}):
        with patch("scout.reviewer.runner._get_existing_proposals", return_value=[]):
            with patch("anthropic.Anthropic", return_value=mock_client):
                with patch.dict("os.environ", {"ANTHROPIC_API_KEY": "test-key"}):
                    stats = run_review(
                        dry_run=False,
                        queue_dir=queue_dir,
                        threads_dir=threads_dir,
                    )

    assert stats["total_input_tokens"] > 0
    assert stats["total_cost_usd"] > 0
    # Thread JSONL should have been written
    jsonl_files = list(threads_dir.glob("*.jsonl"))
    assert len(jsonl_files) >= 1
