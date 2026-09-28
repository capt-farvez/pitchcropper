# Decisions

## 1. Assumptions and open questions

- The green-threshold detector is a placeholder. It masks the whole green frame, so close-ups and noise
  frames count as boundaries and only black frames are rejected. Kept as is: the detector is the seam, its
  quality is an ML question.
- The boundary moves slowly relative to the frame rate. 2 inspected frames per second is enough for a crop
  with 20 px padding.
- One video, one batch run. No live-stream reconnect, no resume.
- `confidence_threshold` and `crop_search` are validated but unused; they feed a downstream crop step.

Questions for product/ML: minimum analysis rate per sport; what makes a boundary valid beyond area; how long
the boundary may be missing before an operator is told; auth and ordering needs of the real reporting API.

## 2. Validation strictness versus fallback

Fail fast at load, exit code 2, before any video is opened: missing or unparsable config, unknown key,
missing key, out-of-range value, unknown detector type. No key has a default. The prototype's `min_area`
and `sport` defaults disagreed with its own config; that is the failure mode this prevents. The error lists
every problem at once.

The prototype's detector label `sam_mask_v1` is rejected, not aliased. A config that claims a SAM model while
running a colour threshold is the mismatch validation exists to catch.

Only fallback: `analysis_fps` above the source rate means inspect every frame.

Part 3 will add which per-frame problems are skipped and which stop the run.

## 3. Performance trade-offs

Synthetic feed, 1280x720 at 30 fps, single run each:

| Run | Time |
|---|---|
| Prototype, 60 s, every frame | 17.1 s |
| Engine, 60 s, every frame | 6.4 s |
| Engine, 60 s, 2 fps inspected | 0.8 s |
| Engine, 120 s, 2 fps inspected | 1.7 s |

- Skipped frames use `cap.grab()`, which avoids the colour conversion and copy but not the decode. Seeking
  would skip the decode too but is unreliable on mp4. So detection cost follows inspected frames; decode cost
  still follows length. `max_frames` bounds a run when that matters more than coverage.
- `downscale` changes nothing at 2 fps because decode dominates. It exists for a real model whose per-frame
  cost dwarfs the decode.
- The prototype's `time.sleep` per frame was its largest cost and is gone. Frame bounds and HSV thresholds
  are built once.

## 4. AI/LLM disclosure

I used Claude (Claude Code) as a drafting and review assistant. I decided the design: library plus thin entry
point, validated config, detector as the single seam, sampling by analysis rate. Claude drafted each module,
its tests, the Docker setup, the docs and this file, one part at a time. I read, ran and edited every draft
before committing, and I made every commit myself.
