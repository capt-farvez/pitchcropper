# Verification

How to check each part of the assignment yourself. All commands run from the repo root, with the virtual
environment active for the local ones.

## Tests

```bash
pytest -q
```

Expect `59 passed`. Covers config validation, the detector seam, sampling, geometry, logging, the failure
policy, aggregation, wire models, the HTTP client, and every exit-code combination.

The same suite runs inside the Docker build as its own stage. A failing test stops `docker compose build`
before the runner image exists, so a successful build is itself proof the tests passed.

## Part 1: configuration fails fast

```bash
python -m engine --config nope.yaml
```

Expect a `config.invalid` line and exit code 2. Then set `analysis_fps: -1` in `config.yaml` and run again:
the message names `sampling.analysis_fps` and nothing else runs. Restore the value.

## Part 2: work follows the sample, not the length

Run with `analysis_fps: 30`, then with `analysis_fps: 2`, and compare `elapsed_s` and `inspected` on the
`run.done` line. Expect about 6 s and 1800 frames versus under 1 s and 120 frames.

## Part 3: observability and noisy frames

Run and read the log: `run.start`, `run.progress` with percent and ETA, `run.done` with the rejection
counts. Open `run_summary.json` for the same counts, the statistics, and the boundary. Set
`logging.level: DEBUG` to see each rejected frame and its reason.

## Part 4: reporting over the network

```bash
docker compose up -d --build mock_api
docker compose run --rm runner
```

Expect `run.finished exit_code=0 reports_sent=4 reports_failed=0` and container exit code 0. Then open
`http://localhost:5000/api/v1/jobs/events` and see `started` and `completed` with the summary.

## Part 4: a dead reporting service is not a pipeline failure

```bash
docker compose stop mock_api
docker compose run --rm --no-deps runner
```

Expect `reporting.failed` warnings, one `reporting.degraded`, then `run.finished exit_code=3` with the same
`valid` count as before, and container exit code 3. Restart with `docker compose up -d mock_api`.

## Clean clone

Clone into a fresh folder and run only:

```bash
docker compose up --build
```

Expect both images to build, the runner to generate the video, process it, report, and exit 0.
