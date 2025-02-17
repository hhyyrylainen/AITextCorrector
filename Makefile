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

# ollama section

ollama-pull-rocm:
	podman pull ollama/ollama:rocm

ollama-pull-vanilla:
	podman pull ollama/ollama:latest

ollama-run:
	podman run -d --privileged --device /dev/kfd --device /dev/dri -v ollama:/root/.ollama -p 11434:11434 --name ollama --replace ollama/ollama:rocm

ollama-interactive:
	podman exec -it ollama ollama run deepseek-r1:14b

# deepseek-r1:32b

.PHONY: ollama-pull-rocm ollama-pull-vanilla ollama-run ollama-interactive
