from functools import partial
from http.client import responses

from anyio.abc import TaskStatus

from backend.utils.job_queue import JobQueue
from backend.utils.job import Job

from .ollama_client import OllamaClient

class AIManager:
    """
    Main manager of the AI side of things, handles running AI jobs and finding the right model
    """

    def __init__(self):
        self.model = "deepseek-r1:32b"
        self.job_queue = JobQueue()

    def configure_model(self, model: str):
        self.model = model
        print("Changed active model to: ", model)

    def prompt_chat(self, message) -> Job:
        task = Job(partial(AIManager._prompt_chat, message, self.model))

        self.job_queue.submit(task)

        return task


    @staticmethod
    def _prompt_chat(message, model) -> str:
        client = OllamaClient()

        response = client.submit_chat_message(model, message)

        if "error" in response:
            raise Exception(f"Ollama API error: {response['error']}")

        # Convert nanoseconds to seconds
        print("Ollama API took: ", response["total_duration"] / 1_000_000_000)

        return response["message"]["content"]
