# Automated Pitch Boundary & Camera Crop Engine

## Setup guides

| Guide | Use it when |
|---|---|
| [Run with Docker](docs/project-setup-docker.md) | You just want it running. One command, nothing to install. |
| [Run locally with a venv](docs/project-setup-local-venv.md) | You want to edit and run the code directly. |
| [Decisions](DECISIONS.md) | Assumptions, trade-offs, failure policy, AI disclosure. |
| [Verification](docs/verification.md) | You want to check each part of the assignment yourself. |
| [Data](docs/data.md) | Where the data comes from, what the outputs mean, privacy and ethics notes. |

## Overview

A batch pipeline that takes a match video, detects the playing-field boundary in a sample of its frames,
and produces one aggregated result for a downstream camera-crop step. It runs unattended in a container,
logs in a structured form, and reports progress and outcome to the platform over HTTP.

It started as a single-file research prototype. That prototype is preserved in the first commit of this
repository; everything after it is the rework.

## Technology Stack

- **Language:** Python 3.12 in Docker, 3.11 or newer locally
- **Field Detection:** Colour-threshold placeholder behind a swappable detector interface
- **Geometry:** Shapely for polygon derivation and area metrics
- **Video I/O:** OpenCV
- **Validation:** Pydantic for configuration, run summary, and wire payloads
- **Tests:** pytest

## Features

- **Validated configuration.** Every setting in `config.yaml` is typed and range-checked. A bad value stops
  the run before any video is opened.
- **Swappable detector.** The one seam that varies by sport: a detector turns a frame into a field mask.
  Adding one is a class and a registry line.
- **Sampled processing.** Only `sampling.analysis_fps` frames per second are analysed; the rest are skipped
  without detection.
- **Structured logging.** One line per event, text or JSON, with a run id, progress, ETA, and a final summary.
- **Failure policy.** Per-frame problems are counted and skipped; repeated ones stop the run; nothing is
  swallowed. See the exit codes below.
- **Aggregated result.** Every frame lands in one bucket. Metrics use valid frames only. Written to
  `run_summary.json`.
- **Platform reporting.** Progress and lifecycle events posted as validated payloads. A dead reporting
  service never becomes a pipeline failure.

## Quick start

All commands run from the repo root.

### With Docker

Requires Docker Desktop, nothing else.

```bash
docker compose up --build
```

Builds and starts `mock_api` on `http://localhost:5000`, then runs the pipeline in the `runner` container
over a synthetic feed it generates itself. The runner exits 0 when done. Open
`http://localhost:5000/api/v1/jobs/events` to see what it reported. Details in
[Run with Docker](docs/project-setup-docker.md).

### Locally with a venv

Requires Python 3.11 or newer. The pipeline reports to the mock API, so start that first in a second
terminal, or set `reporting.enabled: false` in `config.yaml`.

```bash
python -m venv .venv
.venv\Scripts\Activate.ps1          # Windows PowerShell
# source .venv/bin/activate         # macOS / Linux
pip install -r requirements.txt
python -m engine
```

Generates the synthetic feed if it is missing, then processes it. Details in
[Run locally with a venv](docs/project-setup-local-venv.md).

## Repository layout

| Path | Purpose |
|---|---|
| `engine/` | The pipeline library. `python -m engine` is the entry point. |
| `engine/config.py` | Validated configuration model and loader. |
| `engine/detectors/` | The detector interface and the colour-threshold implementation. |
| `engine/sampling.py`, `engine/geometry.py` | Frame sampling; mask to polygon. |
| `engine/analyzer.py`, `engine/aggregate.py` | The frame loop; bucketing and the run summary. |
| `engine/reporting/` | Wire models and the HTTP client for the platform. |
| `config.yaml` | Pipeline settings. Validated at startup; any bad value stops the run with exit code 2. |
| `tests/` | pytest suite. Run with `pytest -q`. |
| `synthetic_generator.py` | Produces the synthetic match feed used as input. Not modified. |
| `mock_api/` | Stand-in for the platform reporting service. Not modified. |
| `Dockerfile`, `docker-compose.yml` | Container build for the runner and the mock API. |
| `docs/` | Setup guides, verification steps, data notes. |
| `DECISIONS.md` | Assumptions, trade-offs, failure policy, AI disclosure. |
| `LICENSE`, `CITATION.cff` | MIT licence and machine-readable citation. |

## Exit codes

| Code | Meaning |
|---|---|
| 0 | Run completed and every report reached the platform |
| 1 | Run started but could not finish: video unreadable, stream broken, or an unexpected error |
| 2 | Configuration missing, unparsable, or invalid. Nothing was run |
| 3 | Run completed, but one or more reports never reached the platform |

## Performance

Only every n-th frame is analysed, where n comes from the source frame rate and `sampling.analysis_fps`.
Skipped frames are advanced with `cap.grab()` and never reach the detector. Measured on the synthetic feed
(1280x720, 30 fps), same machine, single run:

| Run | Time |
|---|---|
| Prototype, 60 s video, every frame | 17.1 s |
| Engine, 60 s video, every frame (`analysis_fps: 30`) | 6.4 s |
| Engine, 60 s video, `analysis_fps: 2` | 0.8 s |
| Engine, 120 s video, `analysis_fps: 2` | 1.7 s |

Detection cost now follows the inspected frame count. The remaining per-frame cost is the codec decoding
skipped frames, which is why a video twice as long still takes about twice as long at the same setting. To
bound a run outright, set `sampling.max_frames`.
