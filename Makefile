ALL: build-frontend

build-frontend:
	cd frontend && npm run build

# Dev server will run on port http://localhost:3000
frontend-dev-server:
	cd frontend && npm run dev

run: run-backend

requirements:
	(source .venv/bin/activate && cd backend && pip install -r requirements.txt)

run-backend:
	(source .venv/bin/activate && cd backend && uvicorn main:app --reload)

.PHONY: build-frontend run run-backend requirements frontend-dev-server
