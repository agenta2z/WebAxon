"""Argument parser for /kb-* CLI commands.

Parses raw argument strings into structured dicts for each knowledge base command.
"""

from typing import Any, Dict, List, Optional, Tuple


def _split_flags(args: str) -> Tuple[str, Dict[str, str]]:
    """Split a raw argument string into positional text and flag dict.

    Flags are ``--key value`` pairs. Boolean flags like ``--hard`` have no value
    and are stored with the value ``"true"``. Positional text is everything
    that appears before the first flag.

    Returns:
        A tuple of (positional_text, flags_dict).
    """
    tokens = args.split()
    positional_parts: List[str] = []
    flags: Dict[str, str] = {}
    i = 0
    found_flag = False
    while i < len(tokens):
        token = tokens[i]
        if token.startswith("--"):
            found_flag = True
            key = token[2:]  # strip leading --
            # Peek ahead: if next token exists and is not a flag, treat it as the value
            if i + 1 < len(tokens) and not tokens[i + 1].startswith("--"):
                flags[key] = tokens[i + 1]
                i += 2
            else:
                # Boolean flag (no value)
                flags[key] = "true"
                i += 1
        else:
            if not found_flag:
                positional_parts.append(token)
            # Tokens after a flag that aren't consumed as values are ignored
            # to keep parsing predictable. Positional text only comes before flags.
            i += 1
    positional = " ".join(positional_parts)
    return positional, flags

def _extract_spaces(flags: Dict[str, str]) -> Optional[List[str]]:
    """Extract space filter from parsed flags.

    ``--spaces`` (comma-separated) takes precedence over ``--space`` (single).
    Returns ``None`` when neither flag is present.
    """
    if "spaces" in flags:
        return [s.strip() for s in flags["spaces"].split(",") if s.strip()]
    if "space" in flags:
        value = flags["space"].strip()
        return [value] if value else None
    return None


def parse_kb_add(args: str) -> Dict[str, Any]:
    """Parse ``/kb-add <text> [--space S] [--spaces S1,S2]``.

    Positional text (before flags) becomes the content.  Flags are parsed
    separately via ``_split_flags``.

    Returns:
        ``{"text": str, "spaces": list|None}``

    Raises:
        ValueError: If text is empty after stripping whitespace.
    """
    positional, flags = _split_flags(args)
    text = positional.strip()
    if not text:
        raise ValueError("Usage: /kb-add <text> [--space S] [--spaces S1,S2]")
    return {"text": text, "spaces": _extract_spaces(flags)}


def parse_kb_update(args: str) -> Dict[str, Any]:
    """Parse ``/kb-update <natural language description>``.

    All text is treated as the update description.

    Returns:
        ``{"text": str}``

    Raises:
        ValueError: If text is empty after stripping whitespace.
    """
    text = args.strip()
    if not text:
        raise ValueError("Usage: /kb-update <text>")
    return {"text": text}


def parse_kb_del(args: str) -> Dict[str, Any]:
    """Parse ``/kb-del <query>`` or ``/kb-del --id <piece_id> [--hard]``.

    Returns one of:
        ``{"mode": "query", "query": str}``
        ``{"mode": "direct", "piece_id": str, "hard": bool}``

    Raises:
        ValueError: If both query and --id are missing.
    """
    positional, flags = _split_flags(args)

    if "id" in flags:
        piece_id = flags["id"]
        if not piece_id or piece_id == "true":
            raise ValueError("Usage: /kb-del --id <piece_id> [--hard]")
        hard = flags.get("hard") == "true"
        return {"mode": "direct", "piece_id": piece_id, "hard": hard}

    query = positional.strip()
    if not query:
        raise ValueError("Usage: /kb-del <query> or /kb-del --id <piece_id> [--hard]")
    return {"mode": "query", "query": query}


def parse_kb_get(args: str) -> Dict[str, Any]:
    """Parse ``/kb-get <query> [--domain D] [--limit N] [--entity-id ID] [--tags T1,T2] [--space S] [--spaces S1,S2]``.

    Returns:
        ``{"query": str, "domain": str|None, "limit": int|None,
          "entity_id": str|None, "tags": list|None, "spaces": list|None}``

    Raises:
        ValueError: If query is empty or --limit is not a positive integer.
    """
    positional, flags = _split_flags(args)

    query = positional.strip()
    if not query:
        raise ValueError("Usage: /kb-get <query> [--domain D] [--limit N] [--entity-id ID] [--tags T1,T2] [--space S] [--spaces S1,S2]")

    domain: Optional[str] = flags.get("domain")
    entity_id: Optional[str] = flags.get("entity-id")

    limit: Optional[int] = None
    if "limit" in flags:
        try:
            limit = int(flags["limit"])
        except (ValueError, TypeError):
            raise ValueError(f"--limit must be a positive integer, got: {flags['limit']}")
        if limit <= 0:
            raise ValueError(f"--limit must be a positive integer, got: {flags['limit']}")

    tags: Optional[List[str]] = None
    if "tags" in flags:
        tags = [t.strip() for t in flags["tags"].split(",") if t.strip()]

    return {
        "query": query,
        "domain": domain,
        "limit": limit,
        "entity_id": entity_id,
        "tags": tags,
        "spaces": _extract_spaces(flags),
    }


def parse_kb_list(args: str) -> Dict[str, Any]:
    """Parse ``/kb-list [--entity-id ID] [--domain D] [--space S] [--spaces S1,S2]``.

    Returns:
        ``{"entity_id": str|None, "domain": str|None, "spaces": list|None}``
    """
    _, flags = _split_flags(args)
    return {
        "entity_id": flags.get("entity-id"),
        "domain": flags.get("domain"),
        "spaces": _extract_spaces(flags),
    }


def parse_kb_restore(args: str) -> Dict[str, Any]:
    """Parse ``/kb-restore <piece_id>``.

    Returns:
        ``{"piece_id": str}``

    Raises:
        ValueError: If piece_id is empty after stripping whitespace.
    """
    piece_id = args.strip()
    if not piece_id:
        raise ValueError("Usage: /kb-restore <piece_id>")
    return {"piece_id": piece_id}

def parse_kb_review_spaces(args: str) -> Dict[str, Any]:
    """Parse ``/kb-review-spaces [--approve <piece_id>] [--reject <piece_id>]``.

    Modes:
        - No args or empty: list pending suggestions → ``{"mode": "list"}``
        - ``--approve <piece_id>``: apply suggestions → ``{"mode": "approve", "piece_id": str}``
        - ``--reject <piece_id>``: reject suggestions → ``{"mode": "reject", "piece_id": str}``

    Returns:
        ``{"mode": str, "piece_id": str|None}``

    Raises:
        ValueError: If --approve/--reject is given without a piece_id, or both are given.
    """
    _, flags = _split_flags(args)

    has_approve = "approve" in flags
    has_reject = "reject" in flags

    if has_approve and has_reject:
        raise ValueError("Cannot use both --approve and --reject at the same time.")

    if has_approve:
        piece_id = flags["approve"]
        if not piece_id or piece_id == "true":
            raise ValueError("Usage: /kb-review-spaces --approve <piece_id>")
        return {"mode": "approve", "piece_id": piece_id}

    if has_reject:
        piece_id = flags["reject"]
        if not piece_id or piece_id == "true":
            raise ValueError("Usage: /kb-review-spaces --reject <piece_id>")
        return {"mode": "reject", "piece_id": piece_id}

    return {"mode": "list", "piece_id": None}
