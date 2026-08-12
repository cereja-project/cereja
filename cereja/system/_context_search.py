"""Compatibility facade for bounded textual context search."""

from cereja.system._context import (
    ContextCacheWarning,
    ContextResponse,
    ContextResult,
    ContextSnippet,
    SkippedFile,
    context_response_to_dict,
    list_text_context,
    search_text_context,
)

__all__ = [
    "ContextCacheWarning",
    "ContextSnippet",
    "ContextResult",
    "SkippedFile",
    "ContextResponse",
    "search_text_context",
    "list_text_context",
    "context_response_to_dict",
]
