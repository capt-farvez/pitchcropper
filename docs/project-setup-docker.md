# Run with Docker

Requires Docker Desktop. Nothing else needs to be installed.

```bash
docker compose up --build
```

Starts `mock_api` on `http://localhost:5000` and runs the pipeline in the `runner` container.
The runner generates the synthetic video itself, processes it, and exits with code 0.
`mock_api` keeps running.

## Check the reporting service

```
http://localhost:5000/api/v1/jobs/events
```

Returns the events reported so far as JSON. `[]` means none yet.
Opening `http://localhost:5000/` alone gives a 404, since the service has no root page.

## Rerun the pipeline without rebuilding

```bash
docker compose run --rm runner
```

## Stop everything

```bash
docker compose down
```
