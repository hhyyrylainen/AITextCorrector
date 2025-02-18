import asyncio
import os
from typing import Dict

from fastapi import FastAPI, UploadFile, HTTPException
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from ai.ai_manager import AIManager
from ai.ollama_client import OllamaClient
from db.config import ConfigModel
from db.database import database

app = FastAPI()

# Path to the exported static files from Next.js
frontend_build_path = os.path.abspath("../frontend/build")

# Mount the static path for CSS/JS files from the React build
app.mount("/_next", StaticFiles(directory=os.path.join(frontend_build_path, "_next")), name="_next")


# Serving root content like this will break everything
# app.mount("/", StaticFiles(directory=frontend_build_path), name="")


# Add middleware to modify headers
@app.middleware("http")
async def add_no_cache_headers(request, call_next):
    response = await call_next(request)

    # Apply no-cache headers only for non-static file requests
    if "/_next/" not in request.url.path:
        if "/api/" in request.url.path:
            response.headers["Cache-Control"] = "no-store, no-cache, must-revalidate"
        else:
            response.headers["Cache-Control"] = "no-cache, must-revalidate"

        response.headers["Pragma"] = "no-cache"
        response.headers["Expires"] = "0"

    return response


manager = AIManager()


@app.get("/")
async def serve_index():
    # Serve the index.html for the root route
    index_file = os.path.join(frontend_build_path, "index.html")
    return FileResponse(index_file)


@app.get("/api/ping")
async def ping():
    return {"message": "pong"}


# GUI endpoints
@app.post("/api/textAnalysis")
async def text_analysis(file: UploadFile):
    content_type = file.content_type

    contents = await file.read()

    return {"instructions": f"This is {content_type} with length {len(contents)}"}


# General AI endpoints
@app.get("/api/ai/models")
async def get_models():
    return await asyncio.to_thread(OllamaClient().list_available_models)


@app.get("/api/ai/loaded")
async def get_models():
    return await asyncio.to_thread(OllamaClient().list_loaded)


@app.get("/api/ai/ollamaVersion")
async def get_models():
    return await asyncio.to_thread(OllamaClient().get_version)


@app.post("/api/ai/chat/single")
async def get_models(prompt: Dict):
    if "prompt" not in prompt or type(prompt["prompt"]) is not str:
        return {"error": "prompt required as JSON parameter"}

    response = await manager.prompt_chat(prompt["prompt"])

    return {"response": response}


# Config management
@app.get("/api/config")
async def get_config():
    return await database.get_config()


@app.put("/api/config")
async def update_config(new_config: ConfigModel):
    if len(new_config.selectedModel) < 1:
        raise HTTPException(
            status_code=422,
            detail={
                "error": "Validation Error",
                "message": "Selected AI model is missing.",
            },
        )

    await database.update_config(new_config)
    print("Got new config: ", new_config)


# Support for static file serving
@app.get("/{path:path}")
async def serve_other_files(path: str):
    file_path = os.path.join(frontend_build_path, path)

    if os.path.exists(file_path):
        return FileResponse(file_path)
    else:
        # Serve index.html for SPA fallback routing
        return FileResponse(os.path.join(frontend_build_path, "index.html"))
