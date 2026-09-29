# Run locally with a virtual environment

Requires Python 3.11 or newer. All commands run from the repo root.

## 1. Create and activate the virtual environment

```bash
python -m venv .venv
```

Windows (PowerShell):

```powershell
.venv\Scripts\Activate.ps1
```

macOS / Linux:

```bash
source .venv/bin/activate
```

The prompt shows `(.venv)` when it is active.

## 2. Install dependencies

```bash
pip install -r requirements.txt
```

## 3. Start the reporting service

The pipeline posts progress and outcome to the mock API. Without it, every report is retried and the run
ends with exit code 3 after about a minute of waiting. Either run the service in a second terminal:

```bash
cd mock_api
pip install -r requirements.txt
python app.py
```

or, if you only want the video work, set `reporting.enabled: false` in `config.yaml`.

## 4. Run the pipeline

```bash
python -m engine
```

Generates `synthetic_pitch_feed.mp4` in the repo root if it is missing, processes it, logs progress, and
writes `run_summary.json`. Both files are git-ignored. Exit code 0 means every step succeeded; see the exit
code table in the README for the others.

To generate the video on its own:

```bash
python -c "from synthetic_generator import generate_synthetic_video; generate_synthetic_video()"
```

## 5. Run the tests

```bash
pytest -q
```

## 6. Leave the environment

```bash
deactivate
```
