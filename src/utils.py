from __future__ import annotations

from typing import Iterable, Iterator, List, Sequence, TypeVar

T = TypeVar("T")


def chunk_list(items: Sequence[T] | Iterable[T], size: int) -> Iterator[list[T]]:
    """
    Split `items` into lists of length `size`.
    Accepts sequences or generic iterables (materializes iterables).
    """
    if size <= 0:
        raise ValueError("size must be positive")
    if not isinstance(items, list):
        items = list(items)
    for idx in range(0, len(items), size):
        yield list(items[idx : idx + size])

