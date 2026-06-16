"""URL liveness checker.

Walks `/catalog/*.md`, HEADs each `source.url`, and writes a JSON state file
that the dedup engine's pass 4 reads to decide what to auto-archive. The
checker is the only network-touching half of the liveness loop; the dedup
engine stays network-free.
"""

from .check import check_urls_once

__all__ = ["check_urls_once"]
