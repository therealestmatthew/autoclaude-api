"""Tests for scout/reviewer/budget.py — spend math, cap exceeded, price table."""

import json
from datetime import date

from scout.reviewer.budget import Budget, check_budget, token_cost, write_thread_record


class TestTokenCost:
    def test_sonnet_input_only(self):
        cost = token_cost("claude-sonnet-4-6", input_tokens=1_000_000)
        assert abs(cost - 3.00) < 0.001

    def test_sonnet_output_only(self):
        cost = token_cost("claude-sonnet-4-6", output_tokens=1_000_000)
        assert abs(cost - 15.00) < 0.001

    def test_sonnet_cache_read(self):
        cost = token_cost("claude-sonnet-4-6", cache_read_tokens=1_000_000)
        assert abs(cost - 0.30) < 0.001

    def test_opus_input_more_expensive(self):
        s = token_cost("claude-sonnet-4-6", input_tokens=1_000_000)
        o = token_cost("claude-opus-4-7", input_tokens=1_000_000)
        assert o > s

    def test_unknown_model_uses_fallback(self):
        cost = token_cost("unknown-model", input_tokens=1_000_000)
        assert cost > 0  # fallback to opus pricing

    def test_zero_tokens(self):
        assert token_cost("claude-sonnet-4-6") == 0.0


class TestBudget:
    def test_remaining_is_cap_minus_spent(self):
        b = Budget(daily_cap_usd=5.0, spent_today_usd=2.0)
        assert abs(b.remaining_usd - 3.0) < 0.001

    def test_will_exceed_when_spent_gte_cap(self):
        assert Budget(daily_cap_usd=5.0, spent_today_usd=5.0).will_exceed
        assert Budget(daily_cap_usd=5.0, spent_today_usd=6.0).will_exceed
        assert not Budget(daily_cap_usd=5.0, spent_today_usd=4.99).will_exceed

    def test_near_cap_at_80_pct(self):
        assert Budget(daily_cap_usd=5.0, spent_today_usd=4.0).near_cap
        assert not Budget(daily_cap_usd=5.0, spent_today_usd=3.99).near_cap

    def test_remaining_floor_at_zero(self):
        b = Budget(daily_cap_usd=5.0, spent_today_usd=10.0)
        assert b.remaining_usd == 0.0


class TestCheckBudget:
    def test_empty_threads_dir(self, tmp_path):
        budget = check_budget(cap=5.0, today=date(2026, 6, 19), threads_dir=tmp_path)
        assert budget.spent_today_usd == 0.0
        assert budget.daily_cap_usd == 5.0

    def test_reads_reviewer_records(self, tmp_path):
        today = date(2026, 6, 19)
        jsonl = tmp_path / "2026-06-19.jsonl"
        records = [
            {"agent": "scout-reviewer", "model": "claude-sonnet-4-6",
             "input_tokens": 1000, "output_tokens": 100,
             "cache_read_tokens": 0, "cache_write_tokens": 0},
            {"agent": "scout", "model": "claude-sonnet-4-6",
             "input_tokens": 50000, "output_tokens": 5000},  # not reviewer; should be ignored
        ]
        jsonl.write_text("\n".join(json.dumps(r) for r in records) + "\n")

        budget = check_budget(cap=5.0, today=today, threads_dir=tmp_path)
        # 1000 input + 100 output tokens at sonnet pricing
        expected = token_cost("claude-sonnet-4-6", input_tokens=1000, output_tokens=100)
        assert abs(budget.spent_today_usd - expected) < 1e-6

    def test_ignores_other_dates(self, tmp_path):
        yesterday = tmp_path / "2026-06-18.jsonl"
        yesterday.write_text(
            json.dumps({"agent": "scout-reviewer", "model": "claude-sonnet-4-6",
                        "input_tokens": 1_000_000, "output_tokens": 0}) + "\n"
        )
        budget = check_budget(cap=5.0, today=date(2026, 6, 19), threads_dir=tmp_path)
        assert budget.spent_today_usd == 0.0

    def test_malformed_lines_skipped(self, tmp_path):
        today = date(2026, 6, 19)
        jsonl = tmp_path / "2026-06-19.jsonl"
        jsonl.write_text("not-json\n{broken\n")
        budget = check_budget(cap=5.0, today=today, threads_dir=tmp_path)
        assert budget.spent_today_usd == 0.0


class TestWriteThreadRecord:
    def test_creates_file(self, tmp_path):
        write_thread_record(
            {"agent": "scout-reviewer", "model": "x"}, today=date(2026, 6, 19), threads_dir=tmp_path
        )
        f = tmp_path / "2026-06-19.jsonl"
        assert f.exists()
        data = json.loads(f.read_text().strip())
        assert data["agent"] == "scout-reviewer"

    def test_appends(self, tmp_path):
        today = date(2026, 6, 19)
        write_thread_record({"n": 1}, today=today, threads_dir=tmp_path)
        write_thread_record({"n": 2}, today=today, threads_dir=tmp_path)
        lines = (tmp_path / "2026-06-19.jsonl").read_text().splitlines()
        assert len(lines) == 2
