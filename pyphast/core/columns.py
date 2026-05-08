"""Excel column letter ↔ index conversion and validation."""

from __future__ import annotations

import re

_COL_RE = re.compile(r"^[A-Z]+$")


def col_letter_to_index(letter: str) -> int:
    """Convert column letter (e.g. 'A', 'AB', 'EI') to 1-based index."""
    s = letter.strip().upper()
    if not s or not _COL_RE.match(s):
        raise ValueError(f"Invalid column letter: {letter!r}")
    n = 0
    for ch in s:
        n = n * 26 + (ord(ch) - ord("A") + 1)
    if n > 16384:  # Excel maximum (XFD)
        raise ValueError(f"Column letter exceeds Excel maximum: {letter!r}")
    return n


def col_index_to_letter(index: int) -> str:
    """Convert 1-based column index to letter."""
    if index < 1 or index > 16384:
        raise ValueError(f"Column index out of range: {index}")
    s = ""
    while index > 0:
        index, r = divmod(index - 1, 26)
        s = chr(ord("A") + r) + s
    return s


def is_valid_col_letter(letter: str) -> bool:
    try:
        col_letter_to_index(letter)
        return True
    except ValueError:
        return False


def normalise_col_letter(letter: str) -> str:
    """Trim and uppercase. Raises ValueError if invalid."""
    s = letter.strip().upper()
    col_letter_to_index(s)  # validates
    return s
