import asyncio
import os
import re
from asyncio import Lock
from typing import Dict, Optional

from fastapi import FastAPI, UploadFile, HTTPException, Form, File, BackgroundTasks
from fastapi.responses import FileResponse, PlainTextResponse, HTMLResponse
from fastapi.staticfiles import StaticFiles
from starlette.responses import RedirectResponse

from ai.ai_manager import AIManager
from ai.ollama_client import OllamaClient
from db.config import ConfigModel
from db.project import create_project, CorrectionStatus
from db.database import database
from utils.epub import extract_epub_chapters, chapters_to_plain_text
from utils.correction_formatter import format_chapter_corrections_as_text, parse_mode

# FastAPI web app setup
app = FastAPI()

# Path to the exported static files from Next.js
frontend_build_path = os.path.abspath("../frontend/build")

# Mount the static path for CSS/JS files from the React build
app.mount("/_next", StaticFiles(directory=os.path.join(frontend_build_path, "_next")), name="_next")

# Serving root content like this will break everything
# app.mount("/", StaticFiles(directory=frontend_build_path), name="")


# Other setup

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
        _ai_manager_instance.custom_ollama = latest_config.customOllamaUrl

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


############
# API Routes
############
@app.get("/")
async def serve_index():
    # Serve the index.html for the root route
    index_file = os.path.join(frontend_build_path, "index.html")
    return FileResponse(index_file)


@app.get("/api/ping")
async def ping():
    return {"message": "pong"}


###############
# GUI endpoints
###############
@app.post("/api/textAnalysis")
async def text_analysis(file: UploadFile):
    content_type = file.content_type

    excerpt_length = (await database.get_config()).styleExcerptLength

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
    # TODO: reimplement text plain mode (needs paragraph objects)
    # elif content_type == "text/plain":
    #     # Split on blank lines
    #     sections = re.split(r'\n\s*\n', (await file.read()).decode("utf-8"))
    #     return [{"title": "Plain text", "paragraphs": sections}]
    else:
        raise HTTPException(status_code=415, detail="Unsupported media type")


@app.get("/api/ai/status")
async def get_models():
    ai_manager = await get_ai_manager()

    return {"thinking": ai_manager.currently_running, "queueLength": ai_manager.queue_length, "model": ai_manager.model}


# Project management endpoints
@app.get("/api/projects")
async def get_projects():
    return await database.get_projects()


@app.post("/api/projects/generateCorrections")
async def generate_project_corrections(background_tasks: BackgroundTasks = BackgroundTasks()):
    projects = await database.get_projects()

    ai_manager = await get_ai_manager()

    background_tasks.add_task(ai_manager.generate_corrections_for_all, projects, database)


@app.get("/api/projects/{project_id}")
async def get_project(project_id: int):
    return await database.get_project(project_id)


@app.post("/api/projects/{project_id}/generateSummaries")
async def get_project(project_id: int, background_tasks: BackgroundTasks):
    project = await database.get_project(project_id)

    if project is None:
        raise HTTPException(status_code=404, detail="Project not found")

    print("Triggering summary generation for project", project_id)

    ai_manager = await get_ai_manager()

    background_tasks.add_task(ai_manager.generate_summaries, project, database)


@app.post("/api/projects/{project_id}/generateCorrections")
async def generate_project_corrections(project_id: int, background_tasks: BackgroundTasks = BackgroundTasks()):
    """
    Endpoint to request generations of all missing corrections for a specific project. This takes really long.
    :param project_id: The ID of the project to generate corrections for.
    :param background_tasks: Background tasks object to add the task to.
    :return: Success message if the request to generate is successfully queued.
    """
    project = await database.get_project(project_id)
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")

    ai_manager = await get_ai_manager()

    background_tasks.add_task(ai_manager.generate_corrections_for_project, project, database)
    print("Triggered correction generation for entire project:", project.name)

    return {"message": "Correction generation queued"}


# Need to use names the frontend can use
# noinspection PyPep8Naming
@app.post("/api/projects")
async def create_new_project(name: str = Form(), writingStyle: str = Form(), levelOfCorrection: int = Form(),
                             file: UploadFile = File(), background_tasks: BackgroundTasks = BackgroundTasks()):
    content_type = file.content_type

    if content_type == "application/epub+zip":
        chapters = extract_epub_chapters(file.file)
    else:
        raise HTTPException(status_code=415, detail="Unsupported file type to extract")

    config = await database.get_config()

    backend_project = create_project(name, writingStyle, levelOfCorrection, chapters)

    created_id = await database.create_project(backend_project)

    if config.autoSummaries:
        print("Triggering auto summaries for project", created_id)

        project = await database.get_project(created_id)

        if project is None:
            print("Failed to get project after creation. Aborting summary generation.")
        else:
            ai_manager = await get_ai_manager()
            background_tasks.add_task(ai_manager.generate_summaries, project, database)

    return {"id": created_id}


@app.post("/api/projects/{project_id}/updateText")
async def project_update_text(project_id: int, file: UploadFile = File()):
    project = await database.get_project(project_id, include_chapters=False)

    if project is None:
        raise HTTPException(status_code=404, detail="Project not found")

    content_type = file.content_type

    if content_type == "application/epub+zip":
        chapters = extract_epub_chapters(file.file)
    else:
        raise HTTPException(status_code=415, detail="Unsupported file type to extract")

    parsed_data = create_project("dummy", "dummy", 1, chapters)

    await database.update_project_chapters(project, parsed_data.chapters)

    return {"message": "Text updated"}


@app.get("/api/chapters/{chapter_id}")
async def get_chapter(chapter_id: int):
    chapter = await database.get_chapter(chapter_id, include_paragraphs=True)
    if not chapter:
        raise HTTPException(status_code=404, detail="Chapter not found")

    return chapter


@app.post("/api/chapters/{chapter_id}/regenerateSummary")
async def regenerate_chapter_summary(chapter_id: int):
    """
    Endpoint to regenerate the summary for a specific chapter.
    :param chapter_id: The ID of the chapter to regenerate the summary for.
    :return: Success message if the request to regenerate is successfully queued.
    """
    chapter = await database.get_chapter(chapter_id, True)
    if not chapter:
        raise HTTPException(status_code=404, detail="Chapter not found")

    ai_manager = await get_ai_manager()

    try:
        await ai_manager.generate_single_summary(chapter)
    except Exception as e:
        raise HTTPException(status_code=500,
                            detail="Error: " + str(e) + " while regenerating summary. Try again later.")

    await database.update_chapter(chapter)

    return {"message": "Summary regenerated"}


@app.post("/api/chapters/{chapter_id}/generateCorrections")
async def generate_chapter_corrections(chapter_id: int, background_tasks: BackgroundTasks = BackgroundTasks()):
    """
    Endpoint to request generations of all missing corrections for a specific chapter.
    :param chapter_id: The ID of the chapter to generate corrections for.
    :param background_tasks: Background tasks object to add the task to.
    :return: Success message if the request to generate is successfully queued.
    """
    chapter = await database.get_chapter(chapter_id, True)
    if not chapter:
        raise HTTPException(status_code=404, detail="Chapter not found")

    project = await database.get_project_by_chapter(chapter.id)

    ai_manager = await get_ai_manager()

    background_tasks.add_task(ai_manager.generate_corrections, chapter, database, project.correctionStrengthLevel)
    print("Triggered correction generation for chapter:", chapter.name)

    return {"message": "Correction generation queued"}


@app.get("/api/chapters/{chapter_id}/paragraphsWithCorrections")
async def chapter_paragraphs_needing_actions(chapter_id: int):
    """
    Endpoint to get a list of paragraphs with corrections for a specific chapter.
    :param chapter_id: The ID of the chapter the paragraphs belong to.
    :return: On success a list of paragraph ids with corrections.
    """
    try:
        return await database.get_paragraphs_ids_needing_actions(chapter_id)
    except Exception as e:
        raise HTTPException(status_code=500,
                            detail="Error: " + str(e) + " while getting paragraphs with corrections.")


@app.get("/api/chapters/{chapter_id}/acceptedParagraphs")
async def chapter_paragraphs_with_accepted_corrections(chapter_id: int):
    """
    Endpoint to get a list of paragraphs with approved corrections for a specific chapter. To view them for an easy
    list of required corrections.
    :param chapter_id: The ID of the chapter the paragraphs belong to.
    :return: On success a list of paragraph ids with approved corrections.
    """
    try:
        return await database.get_paragraphs_with_accepted_corrections(chapter_id)
    except Exception as e:
        raise HTTPException(status_code=500,
                            detail="Error: " + str(e) + " while getting paragraphs in accepted state.")


@app.get("/api/chapters/{chapter_id}/paragraphs/{paragraph_index}")
async def get_paragraph(chapter_id: int, paragraph_index: int):
    paragraph = await database.get_paragraph(chapter_id, paragraph_index)
    if not paragraph:
        raise HTTPException(status_code=404, detail="Paragraph not found")

    return paragraph


@app.post("/api/chapters/{chapter_id}/paragraphs/{paragraph_index}/generateCorrection")
async def generate_correction(chapter_id: int, paragraph_index: int):
    """
    Generates a correction for a specific paragraph, but doesn't return it
    """
    paragraph = await database.get_paragraph(chapter_id, paragraph_index)
    if not paragraph:
        raise HTTPException(status_code=404, detail="Paragraph not found")

    # Need to get the project for the correction strength setting
    project = await database.get_project_by_chapter(paragraph.partOfChapter)

    # And the chapter to know what the index of it is
    chapter = await database.get_chapter(paragraph.partOfChapter)

    config = await database.get_config()

    ai_manager = await get_ai_manager()

    try:
        # As this is meant to be a fast API don't use re-runs
        # await ai_manager.generate_single_correction(paragraph, chapter, project.correctionStrengthLevel, config.correctionReRuns)
        await ai_manager.generate_single_correction(paragraph, chapter, project.correctionStrengthLevel, 0)

        await database.update_paragraph(paragraph)
    except Exception as e:
        print("Error while generating correction: ", e)
        raise HTTPException(status_code=500,
                            detail="Error: " + str(e) + " while generating correction. Try again later.")


@app.post("/api/chapters/{chapter_id}/paragraphs/{paragraph_index}/clear")
async def clear_paragraph_data(chapter_id: int, paragraph_index: int):
    """
    Clears paragraph data state to allow restarting its correcting
    """
    paragraph = await database.get_paragraph(chapter_id, paragraph_index)
    if not paragraph:
        raise HTTPException(status_code=404, detail="Paragraph not found")

    paragraph.correctedText = None
    paragraph.manuallyCorrectedText = None
    paragraph.correctionStatus = CorrectionStatus.notGenerated

    try:
        await database.update_paragraph(paragraph)
    except Exception as e:
        raise HTTPException(status_code=500,
                            detail="Error: " + str(e) + " while saving paragraph. Try again later.")


@app.post("/api/chapters/{chapter_id}/paragraphs/{paragraph_index}/saveManual")
async def paragraph_save_manual(chapter_id: int, paragraph_index: int, request: Dict):
    """
    Saves a manual edit for a paragraph (or clears it if it is the same as the AI)
    """
    paragraph = await database.get_paragraph(chapter_id, paragraph_index)
    if not paragraph:
        raise HTTPException(status_code=404, detail="Paragraph not found")

    text: str | None = request.get("correctedText", None)

    if text is not None and len(text) < 1:
        text = None

    paragraph.manuallyCorrectedText = text

    # If matches AI then reset
    if paragraph.manuallyCorrectedText == paragraph.correctedText:
        paragraph.manuallyCorrectedText = None
    else:
        paragraph.correctionStatus = CorrectionStatus.reviewed

    try:
        await database.update_paragraph(paragraph)
    except Exception as e:
        raise HTTPException(status_code=500,
                            detail="Error: " + str(e) + " while saving paragraph. Try again later.")


@app.post("/api/chapters/{chapter_id}/paragraphs/{paragraph_index}/approve")
async def paragraph_approve(chapter_id: int, paragraph_index: int, request: Dict):
    """
    Approves a paragraph and optionally saves a manual edit for it
    """
    text: str | None = request.get("correctedText", None)

    if text is not None and len(text) < 1:
        text = None

    paragraph = await database.get_paragraph(chapter_id, paragraph_index)
    if not paragraph:
        raise HTTPException(status_code=404, detail="Paragraph not found")

    if text is not None:
        paragraph.manuallyCorrectedText = text

        # If matches AI then reset
        if paragraph.manuallyCorrectedText == paragraph.correctedText:
            paragraph.manuallyCorrectedText = None

    paragraph.correctionStatus = CorrectionStatus.accepted

    try:
        await database.update_paragraph(paragraph)
    except Exception as e:
        raise HTTPException(status_code=500,
                            detail="Error: " + str(e) + " while saving paragraph. Try again later.")


@app.post("/api/chapters/{chapter_id}/paragraphs/{paragraph_index}/reject")
async def paragraph_reject(chapter_id: int, paragraph_index: int):
    """
    Rejects a paragraph
    """
    paragraph = await database.get_paragraph(chapter_id, paragraph_index)
    if not paragraph:
        raise HTTPException(status_code=404, detail="Paragraph not found")

    paragraph.correctionStatus = CorrectionStatus.rejected

    try:
        await database.update_paragraph(paragraph)
    except Exception as e:
        raise HTTPException(status_code=500,
                            detail="Error: " + str(e) + " while saving paragraph. Try again later.")


##########
# Zen mode
##########
@app.get("/api/redirect/zen/{chapter_id}", response_class=HTMLResponse)
async def redirect_to_zen(chapter_id: int):
    """
    Redirects to the zen page for a specific chapter.
    :param chapter_id: The ID of the chapter.
    :return: On success a redirect to the zen page.
    """
    try:
        corrections = await database.get_paragraphs_ids_needing_actions(chapter_id)
    except Exception as e:
        raise HTTPException(status_code=500,
                            detail="Error: " + str(e) + " while getting paragraphs with corrections.")

    if len(corrections) == 0:
        # Nothing needs to be done, so return a small html page saying so
        first_index = 1
        zen_url = f"/zen?chapterId={chapter_id}&paragraphIndex={first_index}"
        chapter_url = f"/chapter?id={chapter_id}"
        return f"""
            <html>
                <head><title>No Corrections</title></head>
                <body>
                    <h1>There is nothing to correct here.</h1>
                    <p>If you'd still like to visit the Zen page, click the link below:</p>
                    <p><a href="{zen_url}">Go to the Zen page</a></p>
                    <p><a href="{chapter_url}">Or return to the chapter</a></p>
                </body>
            </html>
            """
    # Redirect to the first correction if corrections are found
    return RedirectResponse(url="/zen?chapterId=" + str(chapter_id) + "&paragraphIndex=" + str(corrections[0]))


@app.get("/api/zen/nextParagraph/{chapter_id}")
async def get_next_paragraph(chapter_id: int, current: int, reverse: bool = False):
    # TODO: could probably make the database fetch much more efficient here
    try:
        corrections = await database.get_paragraphs_ids_needing_actions(chapter_id)
    except Exception as e:
        raise HTTPException(status_code=500,
                            detail="Error: " + str(e) + " while getting paragraphs with corrections.")

    if len(corrections) == 0:
        return {"error": "Nothing more to correct"}

    if reverse:
        last_seen = None
        for index in corrections:
            if index < current:
                last_seen = index

        if last_seen is not None:
            return {"next": last_seen}
        else:
            return {"next": corrections[0]}
    else:
        for index in corrections:
            if index > current:
                return {"next": index}

        return {"next": corrections[len(corrections) - 1]}


@app.get("/api/zen/load/{chapter_id}")
async def get_zen_paragraphs(chapter_id: int, current: int):
    # Load the current and nearby paragraphs for correction display in the zen view
    try:
        return await database.get_paragraphs_around(chapter_id, current)
    except Exception as e:
        raise HTTPException(status_code=500,
                            detail="Error: " + str(e) + " while getting paragraphs for zen.")


#######################
# Corrections exporting
#######################
@app.get("/api/export/project/{project_id}/{name}", response_class=PlainTextResponse)
async def export_corrections(project_id: int, name: str, mode: str = "correctionsWithOriginal"):
    try:
        parsed_mode = parse_mode(mode)
    except:
        raise HTTPException(status_code=400, detail="Invalid mode")

    _, name_extension = os.path.splitext(name)

    project = await database.get_project(project_id)
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")

    if name_extension == ".txt":
        text = ""
        for chapter in project.chapters:
            if len(text) > 0:
                text += "\n\n"

            text += f"# Chapter {chapter.chapterIndex} of {len(project.chapters)} - {chapter.name}:\n\n"

            text += await format_chapter_corrections_as_text(chapter, parsed_mode, database)

        return text
    else:
        raise HTTPException(status_code=415, detail="Unsupported file type to export")


@app.get("/api/export/chapter/{chapter_id}/{name}", response_class=PlainTextResponse)
async def export_chapter_corrections(chapter_id: int, name: str, mode: str = "correctionsWithOriginal"):
    try:
        parsed_mode = parse_mode(mode)
    except:
        raise HTTPException(status_code=400, detail="Invalid mode")

    _, name_extension = os.path.splitext(name)

    chapter = await database.get_chapter(chapter_id)
    if not chapter:
        raise HTTPException(status_code=404, detail="Chapter not found")

    if name_extension == ".txt":
        return await format_chapter_corrections_as_text(chapter, parsed_mode, database)
    else:
        raise HTTPException(status_code=415, detail="Unsupported file type to export")


######################
# General AI endpoints
######################
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


###################
# Config management
###################
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

    # Remove a trailing '/' if one exists
    if len(new_config.customOllamaUrl) > 0 and new_config.customOllamaUrl[-1] == '/':
        new_config.customOllamaUrl = new_config.customOllamaUrl[:-1]

    await database.update_config(new_config)

    print("Got new config: ", new_config)


#################################
# Support for static file serving
#################################
@app.get("/{path:path}")
async def serve_other_files(path: str):
    file_path = os.path.join(frontend_build_path, path)
    with_html_extension = file_path + ".html"

    if os.path.exists(file_path):
        return FileResponse(file_path)
    elif os.path.exists(with_html_extension):
        # Need to serve specific html subpages so that routing works
        return FileResponse(with_html_extension)
    elif os.path.exists(os.path.join(file_path, "index.html")):
        # Serving index files for each folder
        return FileResponse(os.path.join(file_path, "index.html"))
    else:
        # Serve index.html for SPA fallback routing
        return FileResponse(os.path.join(frontend_build_path, "index.html"))
