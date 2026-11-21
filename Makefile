# ActionLoop: common tasks. On Windows without make, use scripts/dev.ps1 (see README).
PY ?= python
VENV = backend/.venv
ifeq ($(OS),Windows_NT)
  VPY = $(VENV)/Scripts/python.exe
else
  VPY = $(VENV)/bin/python
endif

.PHONY: setup dev backend frontend build run test test-backend test-frontend docker clean

setup:            ## install backend + frontend dependencies
	$(PY) -m venv $(VENV)
	$(VPY) -m pip install -r backend/requirements-dev.txt
	cd frontend && npm install

backend:          ## API on :8000 with auto-reload
	cd backend && ../$(VPY) -m uvicorn app.main:app --reload --port 8000

frontend:         ## Vite dev server on :5173 (proxies /api to :8000)
	cd frontend && npm run dev

dev:              ## run both (needs a POSIX shell); otherwise run `make backend` and `make frontend` in two terminals
	$(MAKE) -j2 backend frontend

build:            ## production frontend bundle (served by the API)
	cd frontend && npm run build

run: build        ## single-process production-style run on :8000
	cd backend && ../$(VPY) -m uvicorn app.main:app --port 8000

test: test-backend test-frontend

test-backend:
	cd backend && ../$(VPY) -m pytest -q

test-frontend:
	cd frontend && npm test

docker:
	docker compose up --build

clean:
	rm -rf frontend/dist data backend/.pytest_cache
