"""Tests for scout/_container.py.

We pin the flag composition without spawning a container. Drift on this list
is a security regression — see conventions/security.md.
"""

from __future__ import annotations

import pytest

from scout._container import IMAGE_NAME, ContainerError, compose_command, run_clone_container


def test_compose_command_pins_security_flags():
    cmd = compose_command("https://github.com/anthropics/claude-cookbooks")
    # Exact flag set we promised in conventions/security.md.
    assert cmd[0] == "docker"
    assert cmd[1] == "run"
    assert cmd[-1] == IMAGE_NAME
    for required in (
        "--rm",
        "--read-only",
        "--cap-drop", "ALL",
        "--security-opt", "no-new-privileges",
        "--pids-limit", "256",
        "-u", "65532",
    ):
        assert required in cmd, f"missing locked flag pair element: {required}"
    # Tmpfs sized just above the 100 MB total cap.
    tmpfs_idx = cmd.index("--tmpfs")
    assert cmd[tmpfs_idx + 1] == "/work:size=120m,uid=65532"
    # Network is bridge (clone needs it), not host or none.
    net_idx = cmd.index("--network")
    assert cmd[net_idx + 1] == "bridge"


def test_compose_command_passes_repo_url_in_env():
    url = "https://github.com/foo/bar"
    cmd = compose_command(url)
    env_idx = cmd.index("-e")
    assert cmd[env_idx + 1] == f"REPO_URL={url}"


def test_compose_command_rejects_private_url():
    with pytest.raises(ValueError, match="refusing to pass unsafe URL"):
        compose_command("http://127.0.0.1/repo")


def test_compose_command_podman_stub():
    with pytest.raises(NotImplementedError, match="podman"):
        compose_command("https://github.com/foo/bar", runtime="podman")


def test_compose_command_unknown_runtime():
    with pytest.raises(ValueError, match="unknown container runtime"):
        compose_command("https://github.com/foo/bar", runtime="firecracker")


def test_run_clone_container_errors_when_runtime_missing(monkeypatch):
    monkeypatch.setattr("scout._container.shutil.which", lambda _name: None)
    with pytest.raises(ContainerError, match="docker not on PATH"):
        run_clone_container("https://github.com/foo/bar")
