"""Integration: batch run with mixed outcomes."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest

from .conftest import write_queue_item


@pytest.mark.integration
def test_batch_mixed_actions(reviewer_world, make_tool_use_response):
    queue_dir = reviewer_world["queue"]
    threads_dir = reviewer_world["threads"]

    write_queue_item(queue_dir, "high-value-repo")
    write_queue_item(queue_dir, "transient-news")
    write_queue_item(queue_dir, "duplicate-article")

    responses = [
        make_tool_use_response("keep", confidence=0.92),
        make_tool_use_response("discard", confidence=0.97),
        make_tool_use_response("discard", confidence=0.88),
    ]
    mock_client = MagicMock()
    mock_client.messages.create.side_effect = responses

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

    assert stats["processed"] == 3
    assert stats["proposed"] == 3
    assert stats["action_counts"]["keep"] == 1
    assert stats["action_counts"]["discard"] == 2


@pytest.mark.integration
def test_limit_caps_processing(reviewer_world, make_tool_use_response):
    queue_dir = reviewer_world["queue"]
    for i in range(5):
        write_queue_item(queue_dir, f"item-{i}")

    mock_response = make_tool_use_response("discard")
    mock_client = MagicMock()
    mock_client.messages.create.return_value = mock_response

    from scout.reviewer.runner import run_review

    with patch("anthropic.Anthropic", return_value=mock_client):
        with patch.dict("os.environ", {"ANTHROPIC_API_KEY": "test-key"}):
            stats = run_review(dry_run=True, queue_dir=queue_dir, limit=2)

    assert stats["processed"] <= 2


@pytest.mark.integration
def test_parent_child_grouped(reviewer_world, make_tool_use_response):
    """Parent + child get one review call; child gets a proposal too."""
    queue_dir = reviewer_world["queue"]
    threads_dir = reviewer_world["threads"]

    # Parent file
    parent_path = queue_dir / "2026-06-19-governor-abc12345.md"
    parent_path.write_text(
        "---\n"
        "slug: governor\n"
        "kind: repo\n"
        "title: Governor\n"
        "source:\n  url: https://github.com/0xhimanshu/governor\n"
        "discovered:\n  via: hackernews\n"
        "---\nGovernor parent.\n"
    )
    # Child file with relations.parent
    child_path = queue_dir / "2026-06-19-governor-usage-governor-abc12345.md"
    child_path.write_text(
        "---\n"
        "slug: governor-usage-governor\n"
        "kind: skill\n"
        "title: Governor Usage Skill\n"
        "source:\n  url: https://github.com/0xhimanshu/governor/blob/main/SKILL.md\n"
        "discovered:\n  via: hackernews\n"
        "relations:\n  parent: governor\n"
        "---\nChild skill.\n"
    )

    # Only ONE model call (for the parent; child cascades)
    mock_response = make_tool_use_response("keep", confidence=0.87)
    mock_client = MagicMock()
    mock_client.messages.create.return_value = mock_response

    posted = []

    def capture_post(url, payload):
        posted.append(payload)
        return {"id": f"p{len(posted)}"}

    from scout.reviewer.runner import run_review

    with patch("scout.reviewer.runner._post_proposal", side_effect=capture_post):
        with patch("scout.reviewer.runner._get_existing_proposals", return_value=[]):
            with patch("anthropic.Anthropic", return_value=mock_client):
                with patch.dict("os.environ", {"ANTHROPIC_API_KEY": "test-key"}):
                    run_review(
                        dry_run=False,
                        queue_dir=queue_dir,
                        threads_dir=threads_dir,
                    )

    # One model call (parent only); proposals written for both parent and child
    assert mock_client.messages.create.call_count == 1
    assert len(posted) == 2
    target_paths = {p["target_path"] for p in posted}
    assert any("governor-usage-governor" in tp for tp in target_paths)
