"""Formatters for KB CLI command output."""


def truncate_content(content: str, max_len: int = 200) -> str:
    """Truncate content to max_len, appending '...' if truncated."""
    if len(content) <= max_len:
        return content
    return content[:max_len] + "..."


def format_ingestion_result(counts: dict) -> str:
    """Format ingestion counts into a summary line.

    E.g. 'Ingested: 3 pieces, 2 metadata, 4 graph nodes, 3 graph edges'
    """
    return (
        f"Ingested: {counts.get('pieces_created', 0)} pieces, "
        f"{counts.get('metadata_created', 0)} metadata, "
        f"{counts.get('graph_nodes_created', 0)} graph nodes, "
        f"{counts.get('graph_edges_created', 0)} graph edges"
    )


def format_update_results(results: list) -> str:
    """Format update operation results.

    E.g. 'Updated 2 pieces:\n  abc12345 (v1 → v2, replace)\n  def67890 (v1 → v2, merge)'
    """
    if not results:
        return "No matching pieces found"
    lines = [f"Updated {len(results)} piece{'s' if len(results) != 1 else ''}:"]
    for r in results:
        pid = r.get("piece_id", "")[:8]
        old_v = r.get("old_version", "?")
        new_v = r.get("new_version", "?")
        action = r.get("action", "unknown")
        lines.append(f"  {pid} (v{old_v} → v{new_v}, {action})")
    return "\n".join(lines)


def format_delete_candidates(candidates: list) -> str:
    """Format deletion candidates as a numbered list for confirmation.

    E.g. '1. abc12345 "Likes Italian cooking..." (score: 0.95)'
    """
    if not candidates:
        return "No matching pieces found"
    lines = []
    for i, c in enumerate(candidates, 1):
        pid = c.get("piece_id", "")[:8]
        preview = c.get("content_preview", "")
        score = c.get("score", 0.0)
        lines.append(f'{i}. {pid} "{preview}" (score: {score:.2f})')
    return "\n".join(lines)


def format_delete_results(results: list) -> str:
    """Format deletion results.

    E.g. 'Deleted 2 pieces (soft)'
    """
    if not results:
        return "No pieces deleted"
    successful = [r for r in results if r.get("success", False)]
    mode = results[0].get("mode", "soft") if results else "soft"
    return f"Deleted {len(successful)} piece{'s' if len(successful) != 1 else ''} ({mode})"


def format_search_results(results: list) -> str:
    """Format search result dicts into a table string.

    Columns: Piece_ID (first 8 chars), Score, Domain, Type, Content (truncated).
    """
    if not results:
        return "No results found"
    header = f"{'Piece_ID':<10} {'Score':<7} {'Domain':<15} {'Type':<12} Content"
    sep = "-" * len(header)
    lines = [header, sep]
    for r in results:
        pid = r.get("piece_id", "")[:8]
        score = r.get("score", 0.0)
        domain = r.get("domain", "")[:15]
        ktype = r.get("knowledge_type", "")[:12]
        content = truncate_content(r.get("content", ""))
        lines.append(f"{pid:<10} {score:<7.2f} {domain:<15} {ktype:<12} {content}")
    return "\n".join(lines)


def format_list_results(results: list) -> str:
    """Format list result dicts into a table string (no score column, has is_active).

    Columns: Piece_ID (first 8 chars), Domain, Type, Active, Content (truncated).
    """
    if not results:
        return "No knowledge pieces found."
    header = f"{'Piece_ID':<10} {'Domain':<15} {'Type':<12} {'Active':<8} Content"
    sep = "-" * len(header)
    lines = [header, sep]
    for r in results:
        pid = r.get("piece_id", "")[:8]
        domain = r.get("domain", "")[:15]
        ktype = r.get("knowledge_type", "")[:12]
        active = "Yes" if r.get("is_active", False) else "No"
        content = truncate_content(r.get("content", ""))
        lines.append(f"{pid:<10} {domain:<15} {ktype:<12} {active:<8} {content}")
    return "\n".join(lines)


def format_restore_result(result: dict) -> str:
    """Format restore result.

    E.g. 'Restored piece: abc12345' or error message.
    """
    if result.get("success", False):
        return f"Restored piece: {result.get('piece_id', '')}"
    return result.get("message", "Restore failed")


def format_review_spaces_results(results: list) -> str:
    """Format pending space suggestion results.

    Each result has piece_id, summary, current_spaces, suggested_spaces, and reasons.
    """
    if not results:
        return "No pending space suggestions."
    lines = [f"Pending space suggestions ({len(results)}):"]
    lines.append("")
    for r in results:
        pid = r.get("piece_id", "")[:8]
        summary = r.get("summary") or truncate_content(r.get("content", ""), 100)
        current = ", ".join(r.get("current_spaces", []))
        suggested = ", ".join(r.get("suggested_spaces", []))
        reasons = r.get("reasons", [])
        lines.append(f"  {pid}")
        lines.append(f"    Summary:   {summary}")
        lines.append(f"    Current:   [{current}]")
        lines.append(f"    Suggested: [{suggested}]")
        if reasons:
            for reason in reasons:
                lines.append(f"    Reason:    {reason}")
        lines.append("")
    return "\n".join(lines)
