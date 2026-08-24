from __future__ import annotations

import argparse
import json
import subprocess
from pathlib import Path

from .analysis import TimelineAnalyzer, summarize
from .coach import build_coaching_report
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
        "report_kind": "candidate_visual_timeline",
        "label_status": "unreviewed",
        "video": {"filename": info.path.name, "width": info.width, "height": info.height, "fps": info.fps, "duration_s": info.duration_s},
        "character_id": None,
        "character_assignment": "unconfirmed",
        "sample_fps": args.sample_fps,
        "event_counts": summarize(events),
        "events": [event.json() for event in events],
        "ground_truth_labels": [],
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


def coach(args: argparse.Namespace) -> int:
    report = json.loads(Path(args.report).read_text(encoding="utf-8"))
    if report.get("character_id") != args.character or report.get("character_assignment") != "human_confirmed":
        raise SystemExit("refusing to coach an unconfirmed sample; assign the character from a reviewed recording first")
    coaching = build_coaching_report(report, character=args.character)
    Path(args.output).write_text(json.dumps(coaching, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"wrote {coaching['recommendation_count']} coaching recommendations to {args.output}")
    return 0


def assign_character(args: argparse.Namespace) -> int:
    report = json.loads(Path(args.report).read_text(encoding="utf-8"))
    report["character_id"] = args.character
    report["character_assignment"] = "human_confirmed"
    report["assignment_note"] = "Character identity was explicitly confirmed by a reviewer; visual candidates remain unconfirmed."
    Path(args.output).write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"wrote character assignment {args.character} to {args.output}")
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
    coach_parser = subcommands.add_parser("coach", help="generate offline tactical review suggestions")
    coach_parser.add_argument("report")
    coach_parser.add_argument("--output", required=True)
    coach_parser.add_argument("--character", default="urashiki_astro_fisher")
    coach_parser.set_defaults(func=coach)
    assign_parser = subcommands.add_parser("assign-character", help="record a human-confirmed character assignment")
    assign_parser.add_argument("report")
    assign_parser.add_argument("--character", required=True)
    assign_parser.add_argument("--output", required=True)
    assign_parser.set_defaults(func=assign_character)
    args = parser.parse_args()
    return args.func(args)
