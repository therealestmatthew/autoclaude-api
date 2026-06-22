"""Environment health check for FT-AutoClaude.

Validates that the work machine is set up correctly for running the backend,
web app, and CLI tools. Prints a checklist with fix hints for any failures.

Exit code 0 = all green, 1 = one or more issues.

Usage:
    uv run ft-autoclaude-doctor
    uv run ft-autoclaude-doctor --api          # also probe the API at :8000
    uv run ft-autoclaude-doctor --no-color     # plain text (CI-friendly)
"""
from __future__ import annotations

import argparse
import shutil
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Callable

GREEN = "\033[32m"
YELLOW = "\033[33m"
RED = "\033[31m"
DIM = "\033[2m"
BOLD = "\033[1m"
RESET = "\033[0m"


@dataclass
class CheckResult:
    label: str
    status: str       # "ok" | "warn" | "fail" | "info"
    detail: str = ""
    fix: str = ""


def _project_root() -> Path:
    return Path(__file__).resolve().parents[1]


# ---------------------------------------------------------------------------
# Individual checks
# ---------------------------------------------------------------------------


def check_python() -> CheckResult:
    v = sys.version_info
    if v < (3, 11):
        return CheckResult(
            "Python version",
            "fail",
            f"{v.major}.{v.minor}.{v.micro}",
            "Install Python 3.11+ (recommended via `uv python install 3.13`)",
        )
    return CheckResult("Python version", "ok", f"{v.major}.{v.minor}.{v.micro}")


def check_uv() -> CheckResult:
    if shutil.which("uv") is None:
        return CheckResult(
            "uv installed",
            "fail",
            "not found on PATH",
            "Install uv: https://docs.astral.sh/uv/getting-started/installation/",
        )
    try:
        out = subprocess.run(
            ["uv", "--version"], capture_output=True, text=True, timeout=5
        )
        return CheckResult("uv installed", "ok", out.stdout.strip())
    except Exception as e:
        return CheckResult("uv installed", "warn", str(e))


def check_node() -> CheckResult:
    if shutil.which("node") is None:
        return CheckResult(
            "Node.js installed",
            "fail",
            "not found on PATH",
            "Install Node 20+: https://nodejs.org/ (or use nvm / fnm)",
        )
    try:
        out = subprocess.run(
            ["node", "--version"], capture_output=True, text=True, timeout=5
        )
        version = out.stdout.strip().lstrip("v")
        major = int(version.split(".", 1)[0])
        if major < 20:
            return CheckResult(
                "Node.js version",
                "warn",
                f"v{version}",
                "Recommend Node 20+ for Next.js 15. Upgrade via nvm/fnm.",
            )
        return CheckResult("Node.js version", "ok", f"v{version}")
    except Exception as e:
        return CheckResult("Node.js version", "warn", str(e))


def check_npm() -> CheckResult:
    if shutil.which("npm") is None:
        return CheckResult(
            "npm installed",
            "fail",
            "not found on PATH",
            "npm ships with Node — re-check your Node install.",
        )
    return CheckResult("npm installed", "ok")


def check_git_repo(root: Path) -> CheckResult:
    if not (root / ".git").is_dir():
        return CheckResult(
            "Git repo",
            "fail",
            "not inside a git repo",
            "Clone the repo: git clone <url> && cd <repo>",
        )
    try:
        branch = subprocess.run(
            ["git", "rev-parse", "--abbrev-ref", "HEAD"],
            cwd=root,
            capture_output=True,
            text=True,
            timeout=5,
        ).stdout.strip()
        return CheckResult("Git repo", "ok", f"branch `{branch}`")
    except Exception as e:
        return CheckResult("Git repo", "warn", str(e))


def check_venv(root: Path) -> CheckResult:
    venv = root / ".venv"
    if not venv.is_dir():
        return CheckResult(
            ".venv synced",
            "fail",
            "missing",
            "Run: uv sync",
        )
    # Confirm a known dep is installed (ruamel.yaml or yaml, etc.)
    try:
        import yaml  # noqa: F401
        return CheckResult(".venv synced", "ok", "deps installed")
    except ImportError:
        return CheckResult(
            ".venv synced",
            "warn",
            "PyYAML missing — possibly stale env",
            "Run: uv sync",
        )


def check_web_deps(root: Path) -> CheckResult:
    web_root = root / "web" / "apps" / "web"
    if not web_root.is_dir():
        return CheckResult(
            "Web app present",
            "fail",
            f"missing {web_root}",
            "Repo seems incomplete — check the clone",
        )
    if not (web_root / "node_modules").is_dir():
        return CheckResult(
            "Web app deps",
            "fail",
            "node_modules missing",
            f"Run: cd {web_root.relative_to(root)} && npm install",
        )
    return CheckResult("Web app deps", "ok", "node_modules present")


def check_db_migrations(root: Path) -> CheckResult:
    migrations_dir = root / "web" / "migrations" / "versions"
    if not migrations_dir.is_dir():
        return CheckResult(
            "DB migrations",
            "warn",
            "migrations dir missing",
            "Repo seems incomplete",
        )
    revs = sorted(p.stem for p in migrations_dir.glob("*.py") if p.stem != "__init__")
    if not revs:
        return CheckResult("DB migrations", "warn", "no revisions found")
    latest = revs[-1].split("_")[0]
    return CheckResult(
        "DB migrations",
        "info",
        f"latest rev {latest} (API auto-migrates on boot)",
    )


def check_env_files(root: Path) -> CheckResult:
    web_env = root / "web" / "apps" / "web" / ".env.local"
    if web_env.is_file():
        return CheckResult("Web .env.local", "ok", "present")
    example = root / "web" / "apps" / "web" / ".env.example"
    fix = "Optional. Defaults work for local dev."
    if example.is_file():
        fix = f"Optional. Copy from {example.relative_to(root)} if you need to override NEXT_PUBLIC_API_URL."
    return CheckResult("Web .env.local", "info", "not set (using defaults)", fix)


def check_api(timeout: float = 2.0) -> CheckResult:
    """Best-effort health probe of the API at :8000. Only runs with --api."""
    try:
        import urllib.request

        with urllib.request.urlopen("http://localhost:8000/health", timeout=timeout) as r:
            if r.status == 200:
                return CheckResult("API reachable (:8000)", "ok", "healthy")
            return CheckResult(
                "API reachable (:8000)",
                "warn",
                f"HTTP {r.status}",
                "API responding but unhealthy",
            )
    except Exception as e:
        return CheckResult(
            "API reachable (:8000)",
            "warn",
            str(e),
            "Start the API: uv run ft-autoclaude-api",
        )


# ---------------------------------------------------------------------------
# Output rendering
# ---------------------------------------------------------------------------


def _icon(status: str, color: bool) -> str:
    if not color:
        return {"ok": " ✓ ", "warn": " ! ", "fail": " ✗ ", "info": " — "}[status]
    return {
        "ok":   f"{GREEN} ✓ {RESET}",
        "warn": f"{YELLOW} ! {RESET}",
        "fail": f"{RED} ✗ {RESET}",
        "info": f"{DIM} — {RESET}",
    }[status]


def render(results: list[CheckResult], color: bool) -> None:
    title = "FT-AutoClaude environment check"
    bar = "─" * max(len(title), 50)
    print(f"\n{BOLD if color else ''}{title}{RESET if color else ''}")
    print(bar)
    for r in results:
        line = f"{_icon(r.status, color)} {r.label}"
        if r.detail:
            line += f"   {DIM if color else ''}{r.detail}{RESET if color else ''}"
        print(line)
        if r.fix and r.status in {"fail", "warn"}:
            print(f"      ↳ Fix: {r.fix}")
    print(bar)
    counts = {"ok": 0, "warn": 0, "fail": 0, "info": 0}
    for r in results:
        counts[r.status] += 1
    print(
        f"{counts['ok']} ok · {counts['fail']} fail · {counts['warn']} warn · {counts['info']} info"
    )
    print()


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--api",
        action="store_true",
        help="Also probe the API at http://localhost:8000/health",
    )
    parser.add_argument(
        "--no-color",
        action="store_true",
        help="Plain text output (for logs/CI)",
    )
    args = parser.parse_args()
    color = not args.no_color and sys.stdout.isatty()

    root = _project_root()
    checks: list[Callable[[], CheckResult]] = [
        check_python,
        check_uv,
        lambda: check_git_repo(root),
        lambda: check_venv(root),
        check_node,
        check_npm,
        lambda: check_web_deps(root),
        lambda: check_db_migrations(root),
        lambda: check_env_files(root),
    ]
    if args.api:
        checks.append(check_api)

    results = [c() for c in checks]
    render(results, color)
    return 0 if not any(r.status == "fail" for r in results) else 1


if __name__ == "__main__":
    sys.exit(main())
