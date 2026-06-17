"""FastAPI dependency providers.

Centralized so tests can override them with `app.dependency_overrides[...]`
to inject fixture indices without monkey-patching globals.
"""

from __future__ import annotations

from ..cache import CachedIndex, get_cached_index
from ..settings import Settings, get_settings


def get_index_settings() -> Settings:
    return get_settings()


def get_index() -> CachedIndex:
    return get_cached_index(get_settings().repo_root)
