"""Container runtime wrapper for the per-clone sandbox.

The single public function is `run_clone_container(repo_url, *, runtime, timeout)`.
It composes the locked flag list documented in `conventions/security.md`
("Container flags (canonical)"), invokes the configured runtime, and returns
the raw tar bytes the entrypoint wrote to stdout.

Runtime selection:
  - `docker` is the v1 default.
  - `podman` is intentionally a stub that raises `NotImplementedError`. The
    flag composition is identical; what we don't trust yet is the rootless
    podman story on the operator's host. Phase 6 will revisit.

We do not parse, retry, or otherwise interpret the runtime's output here —
that's the extractor's job. This module exists to make the flag list testable
without spawning a real container, and to keep the runtime call site small
and obvious.
"""

from __future__ import annotations

import shutil
import subprocess
from dataclasses import dataclass

from ._security import safe_external_url

IMAGE_NAME = "scout-clone-runner"

# Locked flag list. Drift = security regression. The canonical copy of this
# list lives in conventions/security.md; keep them in sync.
_LOCKED_FLAGS: tuple[str, ...] = (
    "--rm",
    "--network", "bridge",
    "--read-only",
    "--tmpfs", "/work:size=120m,uid=65532",
    "--memory", "512m",
    "--cpus", "1",
    "--cap-drop", "ALL",
    "--security-opt", "no-new-privileges",
    "--pids-limit", "256",
    "-u", "65532",
)

DEFAULT_TIMEOUT_SECONDS = 300


class ContainerError(Exception):
    """Raised when the container runtime is unavailable or exits nonzero."""


class ContainerTimeoutError(ContainerError):
    """Raised when the container exceeds its timeout."""


@dataclass(frozen=True)
class ContainerResult:
    """Result of a clone-container run."""

    stdout: bytes
    stderr: str
    returncode: int


def compose_command(
    repo_url: str,
    *,
    runtime: str = "docker",
    image: str = IMAGE_NAME,
) -> list[str]:
    """Return the argv that would be invoked for `repo_url`.

    Split out from `run_clone_container` so tests can pin the exact flag set
    without spawning a container.
    """
    if runtime == "podman":
        raise NotImplementedError(
            "podman runtime is a v1 stub; only docker is wired up. "
            "See locked_decisions in docs/plans/phase-4-repo-extractor.md."
        )
    if runtime != "docker":
        raise ValueError(f"unknown container runtime: {runtime!r}")

    if not safe_external_url(repo_url):
        raise ValueError(f"refusing to pass unsafe URL to container: {repo_url!r}")

    return [
        runtime, "run",
        *_LOCKED_FLAGS,
        "-e", f"REPO_URL={repo_url}",
        image,
    ]


def run_clone_container(
    repo_url: str,
    *,
    runtime: str = "docker",
    image: str = IMAGE_NAME,
    timeout: int = DEFAULT_TIMEOUT_SECONDS,
) -> ContainerResult:
    """Run the clone-runner image and return its stdout (tar bytes).

    Raises:
      ContainerError: runtime missing, image missing, or nonzero exit.
      ContainerTimeoutError: container exceeded `timeout` seconds.
    """
    if shutil.which(runtime) is None:
        raise ContainerError(f"{runtime} not on PATH; install it before running extract-repo")

    cmd = compose_command(repo_url, runtime=runtime, image=image)

    try:
        proc = subprocess.run(  # noqa: S603 — argv is fully composed, no shell
            cmd,
            capture_output=True,
            timeout=timeout,
            check=False,
        )
    except subprocess.TimeoutExpired as e:
        raise ContainerTimeoutError(
            f"clone-runner exceeded {timeout}s for {repo_url}"
        ) from e

    stderr = (proc.stderr or b"").decode("utf-8", errors="replace")
    if proc.returncode != 0:
        raise ContainerError(
            f"clone-runner exited {proc.returncode} for {repo_url}: {stderr.strip()[:500]}"
        )

    return ContainerResult(stdout=proc.stdout, stderr=stderr, returncode=proc.returncode)
