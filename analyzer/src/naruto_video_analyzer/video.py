from __future__ import annotations

import json
import subprocess
from dataclasses import dataclass
from pathlib import Path
from typing import Iterator

import numpy as np


@dataclass(frozen=True)
class VideoInfo:
    path: Path
    width: int
    height: int
    fps: float
    duration_s: float


def probe(path: str | Path) -> VideoInfo:
    path = Path(path)
    command = [
        "ffprobe", "-v", "error", "-select_streams", "v:0", "-show_entries",
        "stream=width,height,r_frame_rate:format=duration", "-of", "json", str(path),
    ]
    data = json.loads(subprocess.check_output(command, text=True))
    stream = data["streams"][0]
    numerator, denominator = stream["r_frame_rate"].split("/")
    return VideoInfo(path, int(stream["width"]), int(stream["height"]), float(numerator) / float(denominator), float(data["format"]["duration"]))


def frames(path: str | Path, sample_fps: float) -> Iterator[tuple[float, np.ndarray]]:
    """Yield sampled RGB frames without relying on a Python video package."""
    info = probe(path)
    command = [
        "ffmpeg", "-hide_banner", "-loglevel", "error", "-i", str(info.path),
        "-vf", f"fps={sample_fps}", "-f", "rawvideo", "-pix_fmt", "rgb24", "pipe:1",
    ]
    process = subprocess.Popen(command, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    assert process.stdout is not None
    frame_bytes = info.width * info.height * 3
    index = 0
    try:
        while True:
            raw = process.stdout.read(frame_bytes)
            if len(raw) != frame_bytes:
                break
            image = np.frombuffer(raw, dtype=np.uint8).reshape((info.height, info.width, 3))
            yield index / sample_fps, image
            index += 1
    finally:
        process.stdout.close()
        process.wait(timeout=30)

