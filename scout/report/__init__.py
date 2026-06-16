"""Scout report — aggregate the thread log into a markdown rollup.

The aggregator is a pure function over `/command-center/threads/*.jsonl`;
the renderer turns those totals into a deterministic markdown document.
"""

from .aggregate import Totals, aggregate
from .render import render

__all__ = ["Totals", "aggregate", "render"]
