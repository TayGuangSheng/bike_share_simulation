# Backend

FastAPI app for ELEN90061 Dockless Bike-Share.

## Quickstart

Windows (PowerShell):

```powershell
python -m venv .venv
\.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
python -m app.seed
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

macOS/Linux (bash):

```bash
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
python -m app.seed
make dev
```

Open http://localhost:8000/docs

Tip: if you want to use `make` on Windows, install GNU Make (e.g., `choco install make`) and run in Git Bash or WSL.
