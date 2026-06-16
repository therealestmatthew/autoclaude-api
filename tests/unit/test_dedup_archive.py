"""Unit tests for scout.dedup.archive: 404-streak and supersedes-chain rules.

The engine is allowed to auto-archive catalog assets only on objective
signals. These tests pin the rules so a future refactor can't quietly
loosen them.
"""

from __future__ import annotations

from datetime import date

from scout.dedup.archive import (
    should_archive_for_404,
    should_archive_for_supersedes,
)

TODAY = date(2026, 6, 15)


class TestShouldArchiveFor404:
    def test_three_streak_old_enough_archives(self) -> None:
        liveness = {
            "checks": {
                "https://example.com/x": {
                    "404_count": 3,
                    "first_404": "2026-04-15",
                }
            }
        }
        assert should_archive_for_404("https://example.com/x", liveness, today=TODAY)

    def test_three_streak_too_recent_skips(self) -> None:
        # First 404 is 10 days ago — under the 30-day threshold.
        liveness = {
            "checks": {
                "https://example.com/x": {
                    "404_count": 5,
                    "first_404": "2026-06-05",
                }
            }
        }
        assert not should_archive_for_404("https://example.com/x", liveness, today=TODAY)

    def test_streak_under_three_skips(self) -> None:
        liveness = {
            "checks": {
                "https://example.com/x": {
                    "404_count": 2,
                    "first_404": "2026-04-01",
                }
            }
        }
        assert not should_archive_for_404("https://example.com/x", liveness, today=TODAY)

    def test_missing_url_skips(self) -> None:
        assert not should_archive_for_404(
            "https://example.com/missing", {"checks": {}}, today=TODAY,
        )

    def test_empty_liveness_skips(self) -> None:
        # Failure-mode contract: "fewer than 3 runs of evidence" → skip pass 4.
        assert not should_archive_for_404("https://example.com/x", {}, today=TODAY)


class TestShouldArchiveForSupersedes:
    def test_supersedes_old_reviewed_archives(self) -> None:
        fm = {
            "status": "reviewed",
            "updated_at": "2026-04-01",
            "relations": {"supersedes": ["older-asset"]},
        }
        assert should_archive_for_supersedes(fm, today=TODAY)

    def test_supersedes_recent_skips(self) -> None:
        fm = {
            "status": "reviewed",
            "updated_at": "2026-06-01",  # 14 days ago, under threshold.
            "relations": {"supersedes": ["older-asset"]},
        }
        assert not should_archive_for_supersedes(fm, today=TODAY)

    def test_no_supersedes_skips(self) -> None:
        fm = {
            "status": "reviewed",
            "updated_at": "2026-04-01",
            "relations": {"supersedes": []},
        }
        assert not should_archive_for_supersedes(fm, today=TODAY)

    def test_already_archived_skips(self) -> None:
        # Idempotency: re-running pass 4 on an already-archived asset is a
        # no-op (no double-archive).
        fm = {
            "status": "archived",
            "updated_at": "2026-04-01",
            "relations": {"supersedes": ["older-asset"]},
        }
        assert not should_archive_for_supersedes(fm, today=TODAY)

    def test_adopted_status_skips(self) -> None:
        # An asset we actively use shouldn't auto-archive on supersedes —
        # the reviewer made a deliberate adoption call.
        fm = {
            "status": "adopted",
            "updated_at": "2026-04-01",
            "relations": {"supersedes": ["older-asset"]},
        }
        assert not should_archive_for_supersedes(fm, today=TODAY)
