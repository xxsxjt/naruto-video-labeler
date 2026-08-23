from __future__ import annotations

import argparse
import json
import subprocess
from pathlib import Path

from .analysis import TimelineAnalyzer, summarize
from .regions import parse_regions
from .video import frames, probe


def _regions(path: str | None) -> dict:
    config_path = Path(path) if path else Path(__file__).parents[2] / "config" / "default_ui.json"
    return parse_regions(json.loads(config_path.read_text(encoding="utf-8")))


def analyze(args: argparse.Namespace) -> int:
    info = probe(args.input)
    analyzer = TimelineAnalyzer(_regions(args.config), args.visual_change_threshold)
    events = []
    for timestamp_s, frame in frames(args.input, args.sample_fps):
        events.extend(analyzer.process(timestamp_s, frame))
    events.extend(analyzer.finalize())
    events.sort(key=lambda event: event.timestamp_s)
    report = {
        "video": {"filename": info.path.name, "width": info.width, "height": info.height, "fps": info.fps, "duration_s": info.duration_s},
        "sample_fps": args.sample_fps,
        "event_counts": summarize(events),
        "events": [event.json() for event in events],
        "notes": ["Candidate events require human review.", "The tool is offline analysis only and does not generate game controls."],
    }
    Path(args.output).write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"wrote {len(events)} events to {args.output}")
    return 0


def inspect(args: argparse.Namespace) -> int:
    command = ["ffmpeg", "-hide_banner", "-loglevel", "error", "-i", args.input, "-vf", f"fps=1/{args.seconds},scale={args.width}:-2,tile=4x3:padding=6:margin=6", "-frames:v", "1", args.output]
    subprocess.run(command, check=True)
    print(f"wrote contact sheet to {args.output}")
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description="Offline visual event extraction for Naruto Mobile recordings")
    subcommands = parser.add_subparsers(dest="command", required=True)
    common = argparse.ArgumentParser(add_help=False)
    common.add_argument("input")
    analyze_parser = subcommands.add_parser("analyze", parents=[common])
    analyze_parser.add_argument("--output", required=True)
    analyze_parser.add_argument("--config")
    analyze_parser.add_argument("--sample-fps", type=float, default=12.0)
    analyze_parser.add_argument("--visual-change-threshold", type=float, default=28.0)
    analyze_parser.set_defaults(func=analyze)
    inspect_parser = subcommands.add_parser("inspect", parents=[common])
    inspect_parser.add_argument("--output", required=True)
    inspect_parser.add_argument("--seconds", type=float, default=3.0)
    inspect_parser.add_argument("--width", type=int, default=800)
    inspect_parser.set_defaults(func=inspect)
    args = parser.parse_args()
    return args.func(args)
