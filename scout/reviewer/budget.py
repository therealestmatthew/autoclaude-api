"""Daily spend cap for the reviewer agent.

Reads today's reviewer entries from command-center/threads/<date>.jsonl,
sums actual spend, and refuses to invoke the model when the cap is hit.

The Phase 7 token-burn rollup already knows how to aggregate these fields
(input_tokens, output_tokens, cache_read_tokens, cache_write_tokens) — the
reviewer just needs to write them in the same shape.
"""

from __future__ import annotations

import json
import os
from dataclasses import dataclass
from datetime import date
from pathlib import Path
from typing import Any

import yaml

REPO_ROOT = Path(__file__).resolve().parents[2]
_PRICING_PATH = Path(__file__).resolve().parent / "pricing.yaml"
_THREADS_DIR = REPO_ROOT / "command-center" / "threads"

DEFAULT_CAP_USD: float = float(os.environ.get("AUTOCLAUDE_REVIEWER_DAILY_BUDGET", "5.00"))
_WARN_FRACTION = 0.80


def _load_prices() -> dict[str, dict[str, float]]:
    data = yaml.safe_load(_PRICING_PATH.read_text())
    return data["models"]


_PRICES: dict[str, dict[str, float]] = _load_prices()


def token_cost(
    model: str,
    input_tokens: int = 0,
    output_tokens: int = 0,
    cache_read_tokens: int = 0,
    cache_write_tokens: int = 0,
) -> float:
    """Return cost in USD for a single API call."""
    prices = _PRICES.get(model)
    if not prices:
        # Unknown model — use a conservative fallback (Opus rates)
        prices = _PRICES.get("claude-opus-4-7", {"input": 15.0, "output": 75.0,
                                                   "cache_write": 18.75, "cache_read": 1.50})
    per_m = 1_000_000
    return (
        input_tokens * prices["input"] / per_m
        + output_tokens * prices["output"] / per_m
        + cache_read_tokens * prices["cache_read"] / per_m
        + cache_write_tokens * prices["cache_write"] / per_m
    )


def estimate_call_cost(model: str, input_chars: int) -> float:
    """Rough pre-call cost estimate based on character count."""
    # ~3.5 chars per token; assume 200 output tokens
    estimated_input = int(input_chars / 3.5)
    return token_cost(model, input_tokens=estimated_input, output_tokens=200)


@dataclass
class Budget:
    daily_cap_usd: float
    spent_today_usd: float

    @property
    def remaining_usd(self) -> float:
        return max(0.0, self.daily_cap_usd - self.spent_today_usd)

    @property
    def will_exceed(self) -> bool:
        return self.spent_today_usd >= self.daily_cap_usd

    @property
    def near_cap(self) -> bool:
        if self.daily_cap_usd == 0:
            return False
        return self.spent_today_usd / self.daily_cap_usd >= _WARN_FRACTION


def _read_today_spend(today: date, threads_dir: Path) -> float:
    """Sum reviewer token spend from today's thread JSONL."""
    jsonl_path = threads_dir / f"{today.isoformat()}.jsonl"
    if not jsonl_path.exists():
        return 0.0

    total = 0.0
    for line in jsonl_path.read_text().splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            rec = json.loads(line)
        except json.JSONDecodeError:
            continue
        if rec.get("agent") != "scout-reviewer":
            continue
        m = rec.get("model", "")
        total += token_cost(
            model=m,
            input_tokens=rec.get("input_tokens", 0),
            output_tokens=rec.get("output_tokens", 0),
            cache_read_tokens=rec.get("cache_read_tokens", 0),
            cache_write_tokens=rec.get("cache_write_tokens", 0),
        )
    return total


def check_budget(
    cap: float = DEFAULT_CAP_USD,
    today: date | None = None,
    threads_dir: Path = _THREADS_DIR,
) -> Budget:
    """Return current budget state by summing today's reviewer spend."""
    if today is None:
        today = date.today()
    spent = _read_today_spend(today, threads_dir)
    return Budget(daily_cap_usd=cap, spent_today_usd=spent)


def write_thread_record(
    record: dict[str, Any],
    today: date | None = None,
    threads_dir: Path = _THREADS_DIR,
) -> None:
    """Append a JSON line to today's thread JSONL."""
    if today is None:
        today = date.today()
    threads_dir.mkdir(parents=True, exist_ok=True)
    jsonl_path = threads_dir / f"{today.isoformat()}.jsonl"
    with jsonl_path.open("a") as f:
        f.write(json.dumps(record) + "\n")
