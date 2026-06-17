"""Entry point for `uv run autoclaude-api`.

Thin wrapper so the runbook command stays stable even if the FastAPI app
module moves. Delegates to `web.apps.api.main.serve()`.
"""

from __future__ import annotations


def main() -> None:
    from web.apps.api.main import serve

    serve()


if __name__ == "__main__":  # pragma: no cover
    main()
