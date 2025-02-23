import re
from functools import partial
from backend.db.config import DEFAULT_MODEL
from backend.db.database import Database
from backend.db.project import Project
from backend.utils.job import Job
from backend.utils.job_queue import JobQueue
from .ollama_client import OllamaClient

ANALYZE_PROMPT = (
    "Analyze the writing style of the provided text, focusing on key elements such as sentence structure, word choice, "
    "tone, readability, and overall style. Provide a concise, one-paragraph summary of the writing style in the form "
    "of instructions, as if advising someone on how to emulate this style. Avoid commenting on the content itself, "
    "such as the author's expertise or the subject matter—it's only about the writing style.\n"
    "\n"
    "Example output: \"Write using [characteristic 1], [characteristic 2], and [characteristic 3]. "
    "Employ [writing technique 1] and [writing technique 2] to [desired effect]. Maintain a [tone] tone throughout, "
    "and aim for a readability score of [score].\"\n"
    "\n"
    "#TEXT\n"
    "\n")

SUMMARY_PROMPT = (
    "\n---\n"
    "Write a summary of the plot in the above text. Write at most four to five paragraphs of summary of the text with the focus"
    "being on the most important plot points in this chapter. Write about what happened in the chapter without "
    "speculating about the future direction of the story. Also do not comment on the writing style or sophistication of "
    "the text. Assume the target audience of the summary is already familiar with the overall story the chapter is from.")

# If this is too low starts of chapters won't be summarized
# If this cannot be turned high enough then a multipart analysis will need to be done
SUMMARY_CONTEXT_WINDOW_SIZE = 8196

EXTRA_RECOMMENDED_MODELS = ["deepseek-r1:14b"]


class AIManager:
    """
    Main manager of the AI side of things, handles running AI jobs and finding the right model
    """

    def __init__(self):
        self.unload_delay = 300
        self.currently_running = False
        self.model = "deepseek-r1:32b"
        self.job_queue = JobQueue()

    def configure_model(self, model: str):
        self.model = model
        print("Changed active model to: ", model)

    def prompt_chat(self, message, remove_think=False) -> Job:
        task = Job(partial(self._prompt_chat, message, self.model, None, remove_think))

        self.job_queue.submit(task)

        return task

    def analyze_writing_style(self, text) -> Job:
        # TODO: maybe increase context window also here?
        task = Job(partial(self._prompt_chat, ANALYZE_PROMPT + text, self.model, None, True))

        self.job_queue.submit(task)

        return task

    async def generate_summaries(self, project: Project, database: Database):
        for chapter in project.chapters:
            if chapter.summary:
                continue

            print("Generating missing summary for chapter:", chapter.name)

            paragraphs = await database.get_chapter_paragraph_text(chapter.id)

            text = f"Chapter {chapter.chapterIndex}: {chapter.name}\n\n"

            for paragraph in paragraphs:
                text += "\n\n"

                if paragraph.leadingSpace > 0:
                    text += "\n" * paragraph.leadingSpace

                text += paragraph.originalText

            # Increase context length to get full chapter explanations
            extra_options = {"num_ctx": SUMMARY_CONTEXT_WINDOW_SIZE}

            task = Job(
                partial(self._prompt_chat, "Read this text:\n" + text + SUMMARY_PROMPT, self.model, extra_options,
                        True))

            self.job_queue.submit(task)

            response = await task

            if len(response) > 3500:
                response = response[:3500] + "..."

            chapter.summary = response

            await database.update_chapter(chapter)

    def download_recommended(self):
        all_models = [DEFAULT_MODEL] + EXTRA_RECOMMENDED_MODELS

        for model in all_models:
            print("Will download model: ", model)

            task = Job(partial(self._download_model, model))

            self.job_queue.submit(task)

    @property
    def queue_length(self):
        return self.job_queue.task_queue.qsize()

    def _prompt_chat(self, message, model, extra_options=None, remove_think=False) -> str:
        self.currently_running = True
        client = OllamaClient(unload_delay=self.unload_delay)

        response = client.submit_chat_message(model, message, extra_options)
        self.currently_running = False

        if "error" in response:
            raise Exception(f"Ollama API error: {response['error']}")

        # Convert nanoseconds to seconds
        print("Ollama API took: ", response["total_duration"] / 1_000_000_000)

        content = response["message"]["content"]

        if remove_think and content.startswith("<think>"):
            # Remove everything between <think></think> tags
            content = re.sub(r"<think>.*?</think>", "", content, flags=re.DOTALL)

        return content.strip()

    def _download_model(self, model):
        self.currently_running = True
        client = OllamaClient()
        if client.download_model(model):
            print("Downloaded model: ", model)

        self.currently_running = False
