"""Integration: second run on same input writes 0 new proposals."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest

from .conftest import write_queue_item


@pytest.mark.integration
def test_second_run_skips_existing_proposals(reviewer_world, make_tool_use_response):
    """When a candidate already has a pending proposal, the runner skips it."""
    queue_dir = reviewer_world["queue"]
    threads_dir = reviewer_world["threads"]
    write_queue_item(queue_dir, "already-proposed")

    mock_response = make_tool_use_response("keep")
    mock_client = MagicMock()
    mock_client.messages.create.return_value = mock_response

    existing_proposal = [{"id": "existing-1", "status": "pending"}]

    from scout.reviewer.runner import run_review

    with patch("scout.reviewer.runner._post_proposal") as mock_post:
        with patch("scout.reviewer.runner._get_existing_proposals", return_value=existing_proposal):
            with patch("anthropic.Anthropic", return_value=mock_client):
                with patch.dict("os.environ", {"ANTHROPIC_API_KEY": "test-key"}):
                    stats = run_review(
                        dry_run=False,
                        queue_dir=queue_dir,
                        threads_dir=threads_dir,
                    )

    assert stats["processed"] == 0
    assert stats["proposed"] == 0
    assert stats["skipped_existing_proposal"] == 1
    mock_post.assert_not_called()
    mock_client.messages.create.assert_not_called()


@pytest.mark.integration
def test_no_existing_proposal_processes_normally(reviewer_world, make_tool_use_response):
    """When no existing proposal, the runner processes and posts."""
    queue_dir = reviewer_world["queue"]
    threads_dir = reviewer_world["threads"]
    write_queue_item(queue_dir, "fresh-item")

    mock_response = make_tool_use_response("discard")
    mock_client = MagicMock()
    mock_client.messages.create.return_value = mock_response

    from scout.reviewer.runner import run_review

    with patch("scout.reviewer.runner._post_proposal", return_value={"id": "new-1"}):
        with patch("scout.reviewer.runner._get_existing_proposals", return_value=[]):
            with patch("anthropic.Anthropic", return_value=mock_client):
                with patch.dict("os.environ", {"ANTHROPIC_API_KEY": "test-key"}):
                    stats = run_review(
                        dry_run=False,
                        queue_dir=queue_dir,
                        threads_dir=threads_dir,
                    )

    assert stats["processed"] == 1
    assert stats["proposed"] == 1
    assert stats["skipped_existing_proposal"] == 0
