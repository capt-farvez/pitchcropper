# Automated Pitch Boundary & Camera Crop Engine (Prototype)

## Setup guides

| Guide | Use it when |
|---|---|
| [Run with Docker](docs/project-setup-docker.md) | You just want it running. One command, nothing to install. |
| [Run locally with a venv](docs/project-setup-local-venv.md) | You want to edit and run the code directly. |
| [Assignment brief](ASSIGNMENT.md) | You want the original task this repo answers. |

## Overview

This repository contains the v0.1 prototype for the automated pitch-boundary and camera-crop initiative. It is a
computer-vision pipeline designed to ingest multi-camera match video, detect the playing-field boundary in each
frame, and derive a recommended camera crop layout from that boundary.

Currently, this is a synchronous, single-file script primarily used by the research team to validate the detection
approach before it gets built out into a production pipeline.

## Technology Stack

- **Language:** Python 3.12+
- **Field Detection:** Mock segmentation mask (color-threshold placeholder standing in for a real SAM-style model).
- **Geometry:** Shapely, for polygon derivation and spatial checks.
- **Video I/O:** OpenCV (`cv2.VideoCapture`).

## Features

- **Synthetic Feed Generation:** Generates a dummy match-style video so the script runs standalone with no external
  assets.
- **Field-Boundary Detection:** Extracts a mask per frame and derives a boundary polygon from it.
- **Crop Recommendation Inputs:** The boundary polygons produced here are meant to feed a downstream crop-layout
  step (not yet implemented in this prototype).
- **Execution Metrics:** Reports how many frames were processed and how many boundaries were found.

## Quick start

All commands run from the repo root.

### With Docker

Requires Docker Desktop, nothing else.

```bash
# Build the runner and mock API containers, then run the pipeline over a generated synthetic feed
docker compose up --build
```

```bash
# Run the pipeline over a generated synthetic feed
docker compose run --rm --no-deps runner python -c "from synthetic_generator import generate_synthetic_video; generate_synthetic_video()"
```

Starts `mock_api` on `http://localhost:5000` and runs the pipeline in the `runner` container over a
generated synthetic feed. check `http://localhost:5000/api/v1/jobs/events` for the events. Details in [Run with Docker](docs/project-setup-docker.md).

### Locally with a venv

Requires Python 3.11 or newer.

```bash
python -m venv .venv
.venv\Scripts\Activate.ps1          # Windows PowerShell
# source .venv/bin/activate         # macOS / Linux
pip install -r requirements.txt
python -c "from synthetic_generator import generate_synthetic_video; generate_synthetic_video()"
python -m engine
```

Generates the synthetic feed if missing, then processes it. Details in
[Run locally with a venv](docs/project-setup-local-venv.md).

## Repository layout

| Path | Purpose |
|---|---|
| `engine/` | The pipeline library. `python -m engine` is the entry point. |
| `config.yaml` | Pipeline settings. Validated at startup; any bad value stops the run with exit code 2. |
| `tests/` | pytest suite. Run with `pytest -q`. |

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
| `synthetic_generator.py` | Produces the synthetic match feed used as input. |
| `mock_api/` | Stand-in for the platform reporting service. Not modified. |
| `Dockerfile`, `docker-compose.yml` | Container build for the runner and the mock API. |
| `docs/` | Setup guides. |
