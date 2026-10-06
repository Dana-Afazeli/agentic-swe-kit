"""Pure text helpers: the sample the kit ships so that every gate has code to bite on.

Replace it with your project's first unit. Nothing here does I/O (contract `Core is pure`).
"""


def truncate(text: str, limit: int, marker: str = "…") -> str:
    """Return `text` when it fits in `limit` characters; else cut it to `limit`, ending in `marker`.

    A marker longer than the limit is itself cut to the limit. A limit below zero is an error.
    """
    if limit < 0:
        raise ValueError(f"limit must be at least 0, got {limit}")
    if len(text) <= limit:
        return text
    head = max(limit - len(marker), 0)
    return (text[:head] + marker)[:limit]
