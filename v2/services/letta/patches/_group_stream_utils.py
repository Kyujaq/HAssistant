# Utility helpers to be imported by patched group managers.

from typing import AsyncIterable, List, Any

async def collect_async(iterable: AsyncIterable[Any]) -> List[Any]:
    """Collect an async iterable (e.g., step_stream) into a list."""
    out: List[Any] = []
    async for item in iterable:
        out.append(item)
    return out
