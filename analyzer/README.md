# Naruto Mobile Video Analyzer

Offline video-analysis MVP for **Naruto Mobile** practice or replay recordings.

It never connects to a game client and cannot send controls. It reads an MP4 and
produces a reviewable JSON timeline from visual signals:

- motion in the joystick and skill-button regions;
- blue/red ring candidates in the arena;
- health-bar change signals;
- central damage / impact flashes.

The detector deliberately returns evidence and confidence instead of pretending
to know an exact game action. It merges adjacent visual changes into compact
review segments, suppressing most single-frame button flickers. The next step is
to calibrate the regions against more recordings, then label a small evaluation
set before adding OCR or a video model.

## Quick start

```bash
cd naruto-video-analyzer
PYTHONPATH=src python3 -m naruto_video_analyzer analyze \
  ../upload/20789.mp4 --sample-fps 12 --output report-20789.json
```

The built-in implementation uses only Python, NumPy, and `ffmpeg`/`ffprobe`.
Optional OCR and a video model are intentionally out of the critical path.

## JSON output

`events` contains candidate segments such as `skill_1_visual_change`,
`joystick_visual_change`, `impact_or_damage_flash`, and `health_bar_change`.
Each has a timestamp, source region, score, and evidence values including
segment start/end, duration, and observation count. Ring updates are sparse
state observations rather than repeated events. The first
default layout is calibrated for the supplied landscape training recordings;
different aspect ratios should use their own region config.

## Data sources

`config/dataset_sources.json` records the approved data policy and current
source categories. Public tutorials and tournament VODs are reference material
only unless their creator explicitly authorizes ingestion. Training media should
come from owner-supplied or expressly authorized recordings.

`config/sample_manifest.json` ties each owner-provided sample to its generated
report and review state. It deliberately leaves character identity and match
outcome as `unknown` until a reviewer verifies them from the replay.

## Calibration workflow

1. Run `analyze` to generate a candidate report.
2. Open the project’s static review page or `web/annotator.html`, then load the
   recording and its report JSON. Confirm or reject only the candidates; export
   the labels.
3. Adjust normalized regions in `config/default_ui.json` if a phone layout differs.
4. Collect labels for 20–50 short clips using `event_schema.json`.
5. Measure precision/recall for each event before adding OCR or an optional
   video-language model as a *review assistant*.

## Commands

```bash
PYTHONPATH=src python3 -m naruto_video_analyzer inspect input.mp4 --output contact.jpg
PYTHONPATH=src python3 -m naruto_video_analyzer analyze input.mp4 --output report.json
```
