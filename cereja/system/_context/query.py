"""Pure query semantics for textual context search."""

from .models import ContextResponse, ContextResult, ContextSnippet


def build_search_result(
        *, path, root, relative_path, size_bytes, text,
        terms, max_snippets, max_snippet_chars,
):
    """Return (ContextResult | None, snippets_truncated)."""
    result = build_search_candidate(
        path=path,
        root=root,
        relative_path=relative_path,
        size_bytes=size_bytes,
        folded_text=text.casefold(),
        terms=terms,
    )
    if result is None:
        return None, False
    snippets, snippets_truncated = extract_snippets(
        text, terms, max_snippets, max_snippet_chars
    )
    return ContextResult(
        path=result.path,
        root=result.root,
        relative_path=result.relative_path,
        size_bytes=result.size_bytes,
        score=result.score,
        match_count=result.match_count,
        snippets=snippets,
    ), snippets_truncated


def build_search_candidate(
        *, path, root, relative_path, size_bytes, folded_text, terms,
):
    """Build a snippet-free result from normalized searchable content."""
    counts = tuple(folded_text.count(term) for term in terms)
    if not all(counts):
        return None
    match_count = sum(counts)
    filename = relative_path.rsplit("/", 1)[-1].casefold()
    filename_hits = sum(term in filename for term in terms)
    score = filename_hits * 1000 + match_count
    return ContextResult(
        path=path,
        root=root,
        relative_path=relative_path,
        size_bytes=size_bytes,
        score=score,
        match_count=match_count,
        snippets=(),
    )


def extract_snippets(text, terms, max_snippets, max_snippet_chars):
    """Return bounded snippets and whether content was omitted."""
    matching = []
    characters_truncated = False
    for line_number, line in enumerate(text.splitlines(), start=1):
        folded_line = line.casefold()
        if any(term in folded_line for term in terms):
            matching.append(ContextSnippet(
                line_number,
                _snippet_window(line, folded_line, terms, max_snippet_chars),
            ))
            characters_truncated = characters_truncated or len(line) > max_snippet_chars
    return (
        tuple(matching[:max_snippets]),
        len(matching) > max_snippets or characters_truncated,
    )


def finalize_response(
        *, mode, query, roots, results, skipped,
        max_results, snippets_truncated,
):
    """Apply stable ordering, bounds, and response truncation."""
    results = tuple(results)
    selected_results = select_context_results(results, mode, max_results)
    sorted_skipped = tuple(
        sorted(skipped, key=lambda item: (item.path.casefold(), item.path))
    )
    results_truncated = len(results) > max_results
    skipped_truncated = len(sorted_skipped) > max_results
    return ContextResponse(
        schema_version=1,
        mode=mode,
        query=query,
        roots=roots,
        results=selected_results,
        skipped=sorted_skipped[:max_results],
        truncated=results_truncated or skipped_truncated or snippets_truncated,
    )


def order_context_results(results, mode):
    """Return results in the stable order for search or list mode."""
    key = (
        (lambda item: (-item.score, item.path.casefold(), item.path))
        if mode == "search"
        else (lambda item: (item.path.casefold(), item.path))
    )
    return tuple(sorted(results, key=key))


def select_context_results(results, mode, max_results):
    """Return the bounded stable selection for search or list mode."""
    return order_context_results(results, mode)[:max_results]


def context_response_to_dict(response):
    """Convert a context response into stable JSON schema version 1."""
    return {
        "schema_version": response.schema_version,
        "mode": response.mode,
        "query": response.query,
        "roots": list(response.roots),
        "results": [
            {
                "path": item.path,
                "root": item.root,
                "relative_path": item.relative_path,
                "size_bytes": item.size_bytes,
                "score": item.score,
                "match_count": item.match_count,
                "snippets": [
                    {"line": snippet.line, "text": snippet.text}
                    for snippet in item.snippets
                ],
            }
            for item in response.results
        ],
        "skipped": [
            {"path": item.path, "reason": item.reason}
            for item in response.skipped
        ],
        "truncated": response.truncated,
    }


def _snippet_window(line, folded_line, terms, max_snippet_chars):
    if len(line) <= max_snippet_chars:
        return line
    occurrences = [
        (folded_line.find(term), term)
        for term in terms
        if folded_line.find(term) >= 0
    ]
    first_match, term = min(occurrences, key=lambda item: item[0])
    leading_context = max(0, max_snippet_chars - len(term)) // 2
    start = max(0, first_match - leading_context)
    start = min(start, len(line) - max_snippet_chars)
    return line[start:start + max_snippet_chars]
