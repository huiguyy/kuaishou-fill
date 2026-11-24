"""Small asynchronous pauses inspired by ZJU-REAL/Easel human pacing (Apache-2.0)."""
from __future__ import annotations

import asyncio
import os
import random

_RANGES_MS = {
    "task-switch": (1800, 4500),
    "field-switch": (650, 1800),
    "review": (2000, 5000),
}


def sample_ms(stage: str, content_length: int = 0, rng=random.random) -> int:
    lo, hi = _RANGES_MS[stage]
    centered = (rng() + rng()) / 2
    review_extra = min(4000, max(0, content_length) * 8) if stage == "review" else 0
    return round(lo + (hi - lo) * centered + review_extra)


async def apace(stage: str, content_length: int = 0) -> None:
    if os.environ.get("FILLUP_PACE_SKIP") == "1":
        return
    await asyncio.sleep(sample_ms(stage, content_length) / 1000)
