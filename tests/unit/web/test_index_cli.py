"""Tests for `ft-autoclaude-index` argparse + subcommand wiring."""

from __future__ import annotations

import shutil
from pathlib import Path

import pytest

from tools.index import build_parser, main
from web.apps.api.settings import reset_settings


@pytest.fixture(autouse=True)
def _isolate_settings(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    """Each CLI test gets its own repo root + DSN so the process singletons
    inside `settings`/`cache` don't leak across cases."""
    repo = tmp_path / "repo"
    fixture = (
        Path(__file__).resolve().parents[2] / "fixtures" / "web" / "sample_repo"
    )
    shutil.copytree(fixture, repo)
    monkeypatch.setenv("FT_AUTOCLAUDE_REPO_ROOT", str(repo))
    monkeypatch.setenv(
        "FT_AUTOCLAUDE_INDEX_DSN", f"sqlite:///{(tmp_path / 'idx.sqlite').as_posix()}"
    )
    reset_settings()
    yield
    reset_settings()


def test_parser_requires_subcommand() -> None:
    parser = build_parser()
    with pytest.raises(SystemExit):
        parser.parse_args([])


def test_sync_subcommand(capsys: pytest.CaptureFixture[str]) -> None:
    # `sync` against a fresh DB requires the tables to exist; upgrade first.
    assert main(["upgrade"]) == 0
    assert main(["sync"]) == 0
    err = capsys.readouterr().err
    assert "sync ok" in err


def test_status_before_any_sync(capsys: pytest.CaptureFixture[str]) -> None:
    assert main(["upgrade"]) == 0
    rc = main(["status"])
    assert rc == 0
    assert "no sync has run yet" in capsys.readouterr().err


def test_status_after_sync(capsys: pytest.CaptureFixture[str]) -> None:
    main(["upgrade"])
    main(["sync"])
    capsys.readouterr()  # drain
    main(["status"])
    err = capsys.readouterr().err
    assert "ft-autoclaude index status" in err
    assert "schema_version" in err


def test_reset_without_yes_refuses() -> None:
    main(["upgrade"])
    rc = main(["reset"])
    assert rc == 2


def test_reset_with_yes_runs_through(capsys: pytest.CaptureFixture[str]) -> None:
    main(["upgrade"])
    main(["sync"])
    capsys.readouterr()
    rc = main(["reset", "--yes"])
    assert rc == 0
    assert "sync ok" in capsys.readouterr().err
