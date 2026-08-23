# MVP validation

Validated on the six user-supplied recordings at four sampled frames per second.
The tool completed without decode errors and wrote one JSON report per input.

| Recording | Duration | Candidate events |
| --- | ---: | ---: |
| 20143.mp4 | 14.80 s | 125 |
| 20789.mp4 | 30.26 s | 137 |
| 2096.mp4 | 30.26 s | 167 |
| 2097.mp4 | 9.45 s | 68 |
| 2514.mp4 | 9.70 s | 85 |
| 2636.mp4 | 30.25 s | 184 |

The results are **candidate observations**, not ground-truth input labels.
In particular, bright character effects can still cause false positives in an
overlapping button crop. Before training or quantitative claims, manually label
the event schema for 20–50 short clips and tune each region against that set.

The included `report-20789.json` is an example output. It contains no input
automation and only references the local source-video path used during testing.
