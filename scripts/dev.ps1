# Windows helper (no `make` needed).
#   .\scripts\dev.ps1 setup   - create venv + install deps
#   .\scripts\dev.ps1 dev     - API (:8000) and Vite (:5173) in two windows
#   .\scripts\dev.ps1 run     - build frontend, serve everything on :8000
#   .\scripts\dev.ps1 test    - run backend + frontend tests
param([Parameter(Position = 0)][ValidateSet("setup", "dev", "run", "test")][string]$Task = "dev")
$ErrorActionPreference = "Stop"
$root = Split-Path $PSScriptRoot -Parent
$py = Join-Path $root "backend\.venv\Scripts\python.exe"

switch ($Task) {
  "setup" {
    python -m venv (Join-Path $root "backend\.venv")
    & $py -m pip install -r (Join-Path $root "backend\requirements-dev.txt")
    Push-Location (Join-Path $root "frontend"); npm install; Pop-Location
  }
  "dev" {
    Start-Process powershell -ArgumentList "-NoExit", "-Command", "cd '$root\backend'; & '$py' -m uvicorn app.main:app --reload --port 8000"
    Push-Location (Join-Path $root "frontend"); npm run dev; Pop-Location
  }
  "run" {
    Push-Location (Join-Path $root "frontend"); npm run build; Pop-Location
    Push-Location (Join-Path $root "backend"); & $py -m uvicorn app.main:app --port 8000; Pop-Location
  }
  "test" {
    Push-Location (Join-Path $root "backend"); & $py -m pytest -q; Pop-Location
    Push-Location (Join-Path $root "frontend"); npm test; Pop-Location
  }
}
