from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Iterable

import numpy as np

from .regions import Region


INPUT_REGIONS = ("joystick", "attack", "skill_1", "skill_2", "substitution", "summon_or_secret")


@dataclass(frozen=True)
class Event:
    timestamp_s: float
    event: str
    score: float
    source: str
    evidence: dict[str, float]

    def json(self) -> dict:
        return asdict(self)


@dataclass
class _ActiveCandidate:
    event: str
    source: str
    start_s: float
    end_s: float
    peak_score: float
    evidence: dict[str, float]
    observations: int = 1

    def extend(self, timestamp_s: float, score: float, evidence: dict[str, float]) -> None:
        self.end_s = timestamp_s
        self.observations += 1
        if score >= self.peak_score:
            self.peak_score = score
            self.evidence = evidence


def _crop(frame: np.ndarray, region: Region) -> np.ndarray:
    rows, cols = region.pixels(frame.shape[1], frame.shape[0])
    return frame[rows, cols]


def _motion(current: np.ndarray, previous: np.ndarray) -> float:
    if current.shape != previous.shape:
        return 0.0
    return float(np.mean(np.abs(current.astype(np.int16) - previous.astype(np.int16))))


def _ring_candidate(frame: np.ndarray, region: Region, color: str) -> tuple[float, float, float]:
    """Return confidence and normalized centroid from a coarse arena colour mask."""
    crop = _crop(frame, region)
    red, green, blue = (crop[..., index].astype(np.int16) for index in range(3))
    if color == "blue":
        mask = (blue > 125) & (blue > red + 30) & (blue > green + 10)
    else:
        mask = (red > 150) & (red > green + 35) & (red > blue + 35)
    ys, xs = np.where(mask)
    if len(xs) < 40:
        return 0.0, 0.0, 0.0
    confidence = min(1.0, len(xs) / max(1, crop.shape[0] * crop.shape[1] * 0.012))
    return confidence, float(np.mean(xs) / crop.shape[1]), float(np.mean(ys) / crop.shape[0])


class TimelineAnalyzer:
    """Extract compact review segments, not one event for every changed frame.

    Raw UI motion is noisy: a skill animation, damage flash, and button glow can
    persist across several sampled frames.  This class merges those observations
    into one candidate segment and emits it only after the signal has ended.
    """

    def __init__(
        self,
        regions: dict[str, Region],
        visual_change_threshold: float = 28.0,
        merge_gap_s: float = 0.35,
        ring_min_interval_s: float = 0.6,
    ):
        self.regions = regions
        self.threshold = visual_change_threshold
        self.merge_gap_s = merge_gap_s
        self.ring_min_interval_s = ring_min_interval_s
        self.previous: dict[str, np.ndarray] = {}
        self.active: dict[tuple[str, str], _ActiveCandidate] = {}
        self.last_ring_observation: dict[str, tuple[float, float, float]] = {}

    def _flush(self, key: tuple[str, str]) -> Event | None:
        candidate = self.active.pop(key, None)
        if candidate is None:
            return None
        # Single-frame generic button flickers are mostly UI noise.  Impact
        # flashes are kept because they are intentionally short.
        if candidate.observations < 2 and candidate.source not in {"impact_area"}:
            return None
        evidence = {
            **candidate.evidence,
            "segment_start_s": candidate.start_s,
            "segment_end_s": candidate.end_s,
            "duration_s": max(0.0, candidate.end_s - candidate.start_s),
            "observations": float(candidate.observations),
        }
        midpoint = (candidate.start_s + candidate.end_s) / 2
        return Event(midpoint, candidate.event, candidate.peak_score, candidate.source, evidence)

    def _observe(
        self,
        timestamp_s: float,
        event: str,
        source: str,
        score: float,
        evidence: dict[str, float],
    ) -> list[Event]:
        key = (event, source)
        emitted: list[Event] = []
        active = self.active.get(key)
        if active and timestamp_s - active.end_s <= self.merge_gap_s:
            active.extend(timestamp_s, score, evidence)
            return emitted
        if active:
            flushed = self._flush(key)
            if flushed:
                emitted.append(flushed)
        self.active[key] = _ActiveCandidate(event, source, timestamp_s, timestamp_s, score, evidence)
        return emitted

    def _expire(self, timestamp_s: float) -> list[Event]:
        emitted: list[Event] = []
        for key, candidate in list(self.active.items()):
            if timestamp_s - candidate.end_s > self.merge_gap_s:
                flushed = self._flush(key)
                if flushed:
                    emitted.append(flushed)
        return emitted

    def finalize(self) -> list[Event]:
        """Flush candidates that are still active at the final video frame."""
        emitted: list[Event] = []
        for key in list(self.active):
            flushed = self._flush(key)
            if flushed:
                emitted.append(flushed)
        return emitted

    def process(self, timestamp_s: float, frame: np.ndarray) -> list[Event]:
        events = self._expire(timestamp_s)
        for name in INPUT_REGIONS:
            if name not in self.regions:
                continue
            crop = _crop(frame, self.regions[name])
            previous = self.previous.get(name)
            if previous is not None:
                score = _motion(crop, previous)
                if score >= self.threshold:
                    events.extend(self._observe(
                        timestamp_s,
                        f"{name}_visual_change",
                        name,
                        score,
                        {"mean_pixel_delta": score},
                    ))
            self.previous[name] = crop.copy()

        for color in ("blue", "red"):
            if "arena" not in self.regions:
                continue
            confidence, x, y = _ring_candidate(frame, self.regions["arena"], color)
            # Rings are state observations.  Keep the initial position, then
            # only record meaningful movement or a sparse heartbeat.
            previous_ring = self.last_ring_observation.get(color)
            elapsed = float("inf") if previous_ring is None else timestamp_s - previous_ring[0]
            moved = previous_ring is None or abs(x - previous_ring[1]) + abs(y - previous_ring[2]) >= 0.08
            stale = previous_ring is None or elapsed >= 3.0
            # The colour mask can jitter on effects.  Position observations at
            # about 1.7 Hz are sufficient for a reviewer and avoid turning a
            # single moving ring into twelve records per second.
            rate_limited = previous_ring is None or elapsed >= self.ring_min_interval_s
            if confidence >= 0.12 and rate_limited and (moved or stale):
                events.append(Event(timestamp_s, f"{color}_ring_state", confidence, "arena", {"arena_x": x, "arena_y": y}))
                self.last_ring_observation[color] = (timestamp_s, x, y)

        for name, event_name in (("impact_area", "impact_or_damage_flash"), ("self_health", "health_bar_change"), ("enemy_health", "health_bar_change")):
            if name not in self.regions:
                continue
            crop = _crop(frame, self.regions[name])
            previous = self.previous.get(name)
            if previous is not None:
                score = _motion(crop, previous)
                threshold = 35.0 if name == "impact_area" else 18.0
                if score >= threshold:
                    events.extend(self._observe(
                        timestamp_s,
                        event_name,
                        name,
                        score,
                        {"mean_pixel_delta": score},
                    ))
            self.previous[name] = crop.copy()
        return events


def summarize(events: Iterable[Event]) -> dict[str, int]:
    result: dict[str, int] = {}
    for event in events:
        result[event.event] = result.get(event.event, 0) + 1
    return result
