# Run with Docker

Requires Docker Desktop. Nothing else needs to be installed.

```bash
docker compose up --build
```

The runner image runs the test suite as a build stage. If any test fails, the build stops there and no
runner image is produced. When the build succeeds, the tests passed.

Starts `mock_api` on `http://localhost:5000` and runs the pipeline in the `runner` container.
The runner generates the synthetic video itself, processes it, writes `run_summary.json` to the repo root,
and exits with code 0. `mock_api` keeps running.

## Where the video is

The runner writes `synthetic_pitch_feed.mp4` to `/app` inside the container. Since the repo folder is
mounted at `/app`, the same file appears in the repo root on your machine. It is git-ignored.

To generate the video without running the pipeline:

```bash
docker compose run --rm --no-deps runner python -c "from synthetic_generator import generate_synthetic_video; generate_synthetic_video()"
```

## Check the reporting service

```
http://localhost:5000/api/v1/jobs/events
```

Returns the events reported so far as JSON: a `started` and a `completed` or `failed` event per run, the
last one carrying the run summary. Progress updates go to `/api/v1/jobs/progress` and show in the
`mock_api` container log.
Opening `http://localhost:5000/` alone gives a 404, since the service has no root page.

## Rerun the pipeline without rebuilding

```bash
docker compose run --rm runner
```

## Stop everything

```bash
docker compose down
```
