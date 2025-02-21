from functools import partial
import re

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


class AIManager:
    """
    Main manager of the AI side of things, handles running AI jobs and finding the right model
    """

    def __init__(self):
        self.currently_running = False
        self.model = "deepseek-r1:32b"
        self.job_queue = JobQueue()

    def configure_model(self, model: str):
        self.model = model
        print("Changed active model to: ", model)

    def prompt_chat(self, message, remove_think=False) -> Job:
        task = Job(partial(self._prompt_chat, message, self.model, remove_think))

        self.job_queue.submit(task)

        return task

    def analyze_writing_style(self, text) -> Job:
        task = Job(partial(self._prompt_chat, ANALYZE_PROMPT + text, self.model, True))

        self.job_queue.submit(task)

        return task

    @property
    def queue_length(self):
        return self.job_queue.task_queue.qsize()

    def _prompt_chat(self, message, model, remove_think=False) -> str:
        self.currently_running = True
        client = OllamaClient()

        response = client.submit_chat_message(model, message)
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
