"""Private components for bounded textual context search."""

from .models import (
    ContextCacheClearReport,
    ContextCacheInfo,
    ContextCacheWarning,
    ContextResponse,
    ContextResult,
    ContextSnippet,
    SkippedFile,
)
from .cache import clear_context_cache, get_context_cache_info
from .cache_db import CacheDatabaseUnavailable
from .query import context_response_to_dict
from .search import list_text_context, search_text_context


__all__ = [
    "ContextCacheInfo",
    "ContextCacheClearReport",
    "ContextCacheWarning",
    "CacheDatabaseUnavailable",
    "ContextSnippet",
    "ContextResult",
    "SkippedFile",
    "ContextResponse",
    "search_text_context",
    "list_text_context",
    "context_response_to_dict",
    "get_context_cache_info",
    "clear_context_cache",
]
