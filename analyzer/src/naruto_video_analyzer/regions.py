from __future__ import annotations

from dataclasses import dataclass
from typing import Mapping


@dataclass(frozen=True)
class Region:
    """A normalized (x, y, width, height) rectangle."""

    x: float
    y: float
    width: float
    height: float

    def pixels(self, frame_width: int, frame_height: int) -> tuple[slice, slice]:
        left = max(0, int(self.x * frame_width))
        top = max(0, int(self.y * frame_height))
        right = min(frame_width, max(left + 1, int((self.x + self.width) * frame_width)))
        bottom = min(frame_height, max(top + 1, int((self.y + self.height) * frame_height)))
        return slice(top, bottom), slice(left, right)


def parse_regions(raw: Mapping[str, list[float]]) -> dict[str, Region]:
    return {name: Region(*values) for name, values in raw.items()}

