# Decisions

## 1. Assumptions and open questions

- The green-threshold detector is a placeholder. It masks the whole green frame, so close-ups and noise
  frames pass as boundaries and only black frames get rejected. I left it alone. The detector is the seam
  that swaps out; how good it is belongs to the ML team.
- The boundary moves slowly compared to the frame rate, so inspecting 2 frames a second is enough for a
  crop with 20 px of padding.
- One video, one batch run. No live-stream reconnect, no resume.
- `confidence_threshold` and `crop_search` are validated but not used yet. They belong to the crop step
  that comes after this one.

Things I would ask before production: what analysis rate each sport actually needs; what makes a boundary
valid beyond its area; how long the pitch can be missing before someone should be told; whether the real
reporting API needs auth or ordering.

## 2. Validation strictness versus fallback

**Config fails at load, exit 2.** Missing file, bad YAML, unknown key, missing key, value out of range,
unknown detector type. No key has a default, because the prototype's defaults for `min_area` and `sport`
disagreed with its own config and nobody would have noticed. The error lists every problem at once.

I rejected the prototype's detector label `sam_mask_v1` instead of aliasing it. A config that says SAM
while running a colour threshold is the kind of lie validation is there to catch.

**One fallback.** Asking for more frames per second than the video has means inspect every frame.

**Run failures, exit 1.** Video will not open, no frame rate, too many failed frames in a row, or anything
unexpected. Unexpected errors are logged with their traceback and still exit 1.

**Per-frame problems are counted, not fatal.** One bad decode, one detector exception, one frame with no
boundary. Each lands in a named bucket and the run continues. The prototype's bare `except` is gone; a
malformed mask is now a counted error instead of a quiet "no boundary".

**Aggregation.** Statistics use valid frames only. The output is one summary: counts per bucket, area and
coverage stats, and the valid polygon of median area as the representative boundary. No valid frames means
null, not zero. `max_coverage` is 1.0 here because the placeholder returns the whole frame, and the summary's
coverage of 1.0 is what tells an operator that.

**Reporting is never a pipeline failure.** A failed request is retried, then counted and logged. After a few
in a row the client stops sending progress so a dead service cannot slow the run, but start and end events
are always tried. A finished run that could not deliver every report exits 3, never 1 and never 0.

The synthetic feed is only generated when nothing is at `video_path`. The prototype regenerated it every run.

## 3. Performance trade-offs

Synthetic feed, 1280x720 at 30 fps, single run each:

| Run | Time |
|---|---|
| Prototype, 60 s, every frame | 17.1 s |
| Engine, 60 s, every frame | 6.4 s |
| Engine, 60 s, 2 fps inspected | 0.8 s |
| Engine, 120 s, 2 fps inspected | 1.7 s |

- Skipped frames go through `cap.grab()`, which skips the colour conversion and copy but not the decode.
  Seeking would skip the decode too, but it is unreliable on mp4. So detection cost follows the frames I
  inspect; decode cost still follows length. `max_frames` caps a run when that matters more.
- `downscale` does nothing at 2 fps because decode dominates. It is there for a real model whose cost per
  frame is far above the decode.
- The prototype's `time.sleep` per frame was its biggest cost. Gone. Frame bounds and HSV thresholds are
  built once.
- A dead reporting service is the one thing that still costs time: about 12 s per failed request in Docker,
  so around a minute before the client gives up on progress. Timeout and retries are config knobs.

## 4. AI/LLM disclosure

I used Claude (Claude Code) throughout. I decided the shape: a library with a thin entry point, a validated
config, the detector as the single seam, sampling by analysis rate. Claude drafted each module, its tests,
the Docker setup, the docs and this file, one part at a time as I asked for them. I read every draft, ran
it locally and in Docker, changed what I disagreed with, and made every commit myself.
