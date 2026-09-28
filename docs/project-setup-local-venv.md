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

## 3. Generate the synthetic video

```bash
python -c "from synthetic_generator import generate_synthetic_video; generate_synthetic_video()"
```

Writes `synthetic_pitch_feed.mp4` to the repo root. The file is git-ignored.

## 4. Run the pipeline

```bash
python synthetic_field_prototype.py
```

Generates the video if it is missing, then processes it and prints the frame and boundary counts.

## 5. Start the reporting service (optional)

The mock API is only needed once the pipeline reports to it. Run it in a second terminal:

```bash
cd mock_api
pip install -r requirements.txt
python app.py
```

Listens on `http://localhost:5000`. Check it with `http://localhost:5000/api/v1/jobs/events`.

## 6. Leave the environment

```bash
deactivate
```
