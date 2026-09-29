# Data

What goes in, what comes out, where it came from, and what it is not.

## Provenance

- **Input video** is generated locally by `synthetic_generator.py`, delivered with the assignment and
  described there as a port of a camera vendor's SDK sample. It is not modified. It draws a green canvas
  with a white quadrilateral that drifts each frame, and inserts three kinds of broadcast artefact: black
  frames (camera cuts, about 1 in 45), plain green frames (close-ups with no pitch, about 1 in 110), and a
  small white rectangle (detection noise, about 1 in 73). 1800 frames at 30 fps, 1280x720, fixed seed.
- **No real footage, no external dataset, no model weights** are used anywhere in this repository.
- **Performance numbers** in the README were measured on this synthetic feed on one developer machine.

## Privacy

The synthetic feed contains no people, no real matches, no venue, and no identifying information. Nothing
in this repository processes or stores personal data. A production deployment on real broadcast video would
process footage of players, staff and spectators, and would need its own privacy assessment before use.

## Ethics

This is a tool for framing a camera on a playing field. It detects a boundary, not people. It should not be
repurposed for tracking or identifying individuals without a separate review. The detector shipped here is a
colour threshold placeholder and its output on real video would be unreliable; do not treat its results as
ground truth.

## Data dictionary

### Input: `config.yaml`

Every key is required. See the comments in the file for the meaning of each. Unknown keys are rejected.

### Output: `run_summary.json`

| Field | Type | Meaning |
|---|---|---|
| `frame_count` | int | Frames in the source video |
| `inspected` | int | Frames actually analysed after sampling |
| `valid` | int | Inspected frames that produced an accepted boundary |
| `rejected` | object | Count per rejection reason, see below |
| `area_px` | object or null | `min`, `median`, `mean`, `max` of boundary area in pixels, over valid frames only |
| `coverage` | object or null | Same statistics for boundary area divided by frame area |
| `boundary` | list of [x, y] or null | Representative boundary: the valid polygon of median area, full-resolution pixel coordinates |
| `boundary_frame_index` | int or null | Frame the representative boundary came from |

`null` means no valid frame was found. It is never reported as zero.

### Rejection reasons

| Reason | Meaning |
|---|---|
| `decode_failed` | Frame was grabbed but the codec could not decode it |
| `detect_failed` | The detector raised an exception on the frame |
| `no_boundary` | No mask, no contour, or the largest contour is below `field_detector.min_area` |
| `invalid_geometry` | The contour is a self-intersecting or degenerate polygon |
| `too_large` | The boundary covers more of the frame than `field_detector.max_coverage` allows |

### Wire payloads

Sent to the reporting service as JSON. Both carry `job_id`, `run_id`, and an ISO 8601 UTC `timestamp`.

| Payload | Endpoint | Extra fields |
|---|---|---|
| `ProgressReport` | `POST /api/v1/jobs/progress` | `frame_index`, `inspected`, `expected_inspected`, `percent`, `valid`, `rejected` |
| `JobEvent` | `POST /api/v1/jobs/events` | `event` (`started`, `completed`, `failed`), `detail`, `summary` (the run summary above, on `completed`) |

### Log records

One per line, text or JSON per `logging.format`. Every record has a timestamp, level, and event name; JSON
records also carry `run_id`. The events an operator watches are `run.start`, `run.progress`, `run.done`,
`run.finished`, and the warnings `frame.decode_failed`, `frame.detect_failed`, `reporting.failed`,
`reporting.degraded`.
