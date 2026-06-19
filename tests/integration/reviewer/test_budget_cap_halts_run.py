"""Integration: daily spend cap stops the runner mid-batch."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest

from .conftest import write_queue_item


@pytest.mark.integration
def test_budget_cap_already_reached_at_startup(reviewer_world):
    """If today's spend already equals the cap, runner refuses to start."""
    queue_dir = reviewer_world["queue"]
    threads_dir = reviewer_world["threads"]
    write_queue_item(queue_dir, "any-item")

    from scout.reviewer.budget import Budget
    from scout.reviewer.runner import run_review

    # Patch check_budget at the runner module level (runner imports _budget_mod)
    with patch("scout.reviewer.runner._budget_mod") as mock_budget:
        mock_budget.check_budget.return_value = Budget(daily_cap_usd=5.0, spent_today_usd=5.00)
        mock_budget.estimate_call_cost.return_value = 0.01

        with patch("anthropic.Anthropic"):
            with patch.dict("os.environ", {"ANTHROPIC_API_KEY": "test-key"}):
                with pytest.raises(SystemExit):
                    run_review(
                        dry_run=False,
                        queue_dir=queue_dir,
                        threads_dir=threads_dir,
                        budget_cap=5.0,
                    )


@pytest.mark.integration
def test_budget_cap_stops_mid_batch(reviewer_world):
    """Once the estimated cost would exceed the cap, stop processing."""
    queue_dir = reviewer_world["queue"]
    threads_dir = reviewer_world["threads"]

    for i in range(5):
        write_queue_item(queue_dir, f"item-{i}")

    block = MagicMock()
    block.type = "tool_use"
    block.name = "emit_decision"
    block.input = {"action": "discard", "confidence": 0.9, "rationale": "Test."}
    usage = MagicMock()
    usage.input_tokens = 1000
    usage.output_tokens = 150
    usage.cache_read_input_tokens = 0
    usage.cache_creation_input_tokens = 0
    mock_response = MagicMock()
    mock_response.content = [block]
    mock_response.usage = usage

    mock_client = MagicMock()
    mock_client.messages.create.return_value = mock_response

    from scout.reviewer.budget import Budget
    from scout.reviewer.runner import run_review

    cap = 0.000001  # effectively zero

    # Patch estimate_call_cost to return a value exceeding cap so budget stops
    with patch("scout.reviewer.runner._budget_mod") as mock_budget:
        from scout.reviewer import budget as real_budget
        mock_budget.check_budget.return_value = Budget(daily_cap_usd=cap, spent_today_usd=0.0)
        mock_budget.estimate_call_cost.return_value = 0.01  # 0.01 >> 0.000001
        mock_budget.write_thread_record = real_budget.write_thread_record
        mock_budget.token_cost = real_budget.token_cost

        with patch("scout.reviewer.runner._post_proposal", return_value={"id": "px"}):
            with patch("scout.reviewer.runner._get_existing_proposals", return_value=[]):
                with patch("anthropic.Anthropic", return_value=mock_client):
                    with patch.dict("os.environ", {"ANTHROPIC_API_KEY": "test-key"}):
                        stats = run_review(
                            dry_run=False,
                            queue_dir=queue_dir,
                            threads_dir=threads_dir,
                            budget_cap=cap,
                        )

    # All 5 should be skipped due to budget
    assert stats["processed"] == 0
    assert stats["skipped_budget"] >= 1
