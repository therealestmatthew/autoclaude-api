"""Scout doctor — catalog integrity checks.

Static checks over `/catalog/` (and the queue, where relevant). Reports
findings; the only thing it auto-fixes is slug↔filename normalization.
Anything richer (orphan children, broken supersedes) surfaces to a human.
"""

from .checks import Finding, run_checks

__all__ = ["Finding", "run_checks"]
