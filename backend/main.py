import asyncio
import os
import re
from asyncio import Lock
from typing import Dict, Optional

from fastapi import FastAPI, UploadFile, HTTPException
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from ai.ai_manager import AIManager
from ai.ollama_client import OllamaClient
from db.config import ConfigModel
from db.database import database
from utils.epub import extract_epub_chapters, chapters_to_plain_text

# FastAPI web app setup
app = FastAPI()

# Path to the exported static files from Next.js
frontend_build_path = os.path.abspath("../frontend/build")

# Mount the static path for CSS/JS files from the React build
app.mount("/_next", StaticFiles(directory=os.path.join(frontend_build_path, "_next")), name="_next")

# Serving root content like this will break everything
# app.mount("/", StaticFiles(directory=frontend_build_path), name="")

downloaded_recommended = False

# Singleton instance of AIManager
_ai_manager_instance: Optional[AIManager] = None
_ai_manager_lock = Lock()


async def get_ai_manager():
    global _ai_manager_instance

    # Get latest config to ensure AI manager can be made up to date
    latest_config = await database.get_config()

    async with _ai_manager_lock:  # Only one coroutine can access this block at a time
        if _ai_manager_instance is None:
            _ai_manager_instance = AIManager()
            _ai_manager_instance.model = latest_config.selectedModel
            print("AI manager started. Model: ", _ai_manager_instance.model)

        if _ai_manager_instance.model != latest_config.selectedModel:
            print("AI manager model changed. Old model: ", _ai_manager_instance.model, "New model: ",
                  latest_config.selectedModel)
            _ai_manager_instance.model = latest_config.selectedModel
        _ai_manager_instance.unload_delay = latest_config.unusedAIUnloadDelay

    return _ai_manager_instance


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

    excerpt_length = (await database.get_config()).textAnalysisExcerptLength

    if content_type == "application/epub+zip":
        chapters = extract_epub_chapters(file.file)
        text = chapters_to_plain_text(chapters, excerpt_length)
    elif content_type == "text/plain":
        text = (await file.read()).decode("utf-8")
        text = text[:excerpt_length]
    else:
        raise HTTPException(status_code=415, detail="Unsupported media type")

    instructions = await (await get_ai_manager()).analyze_writing_style(text)

    return {"instructions": instructions}


@app.post("/api/extractText")
async def extract_text(file: UploadFile):
    content_type = file.content_type

    if content_type == "application/epub+zip":
        return extract_epub_chapters(file.file)
    elif content_type == "text/plain":
        # Split on blank lines
        sections = re.split(r'\n\s*\n', (await file.read()).decode("utf-8"))
        return [{"title": "Plain text", "paragraphs": sections}]
    else:
        raise HTTPException(status_code=415, detail="Unsupported media type")


@app.get("/api/ai/status")
async def get_models():
    ai_manager = await get_ai_manager()

    return {"thinking": ai_manager.currently_running, "queueLength": ai_manager.queue_length, "model": ai_manager.model}


# General AI endpoints
@app.get("/api/ai/models")
async def get_models():
    try:
        return await asyncio.to_thread(OllamaClient().list_available_models)
    except Exception as e:
        return {"error": str(e)}


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

    remove_think = True

    if "removeThink" in prompt and prompt["removeThink"] == False:
        remove_think = False

    response = await (await get_ai_manager()).prompt_chat(prompt["prompt"], remove_think)

    return {"response": response}


@app.post("/api/ai/downloadRecommended")
async def get_models():
    global downloaded_recommended
    if downloaded_recommended:
        return {"error": "recommended models already downloaded"}
    downloaded_recommended = True

    print("Starting download of recommended models... This may take a while. Please wait.")
    (await get_ai_manager()).download_recommended()

    return {"message": "recommended models download started"}


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
