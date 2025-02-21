from typing import Dict, Any

import requests


# TODO: investigate if structured outputs or suffix would be nice

class OllamaClient:
    """
    A client for interacting with the local Ollama API.
    """

    def __init__(self, base_url: str = "http://localhost:11434", unload_delay=None):
        """
        Initialize the OllamaClient with the base URL for the Ollama API.
        
        Args:
            base_url (str): The base URL of the local Ollama API.
            :param unload_delay: None or time in seconds to wait before unloading a model
        """
        self.base_url = base_url
        self.unload_delay = unload_delay

    def submit_chat_message(self, model: str, message: str) -> Dict[str, Any]:
        """
        Sends a message to a specific model in the Ollama API and retrieves the response in a chat format.

        Args:
            model (str): The name of the AI model to use (e.g., "llama2").
            message (str): The content of the message to send.

        Returns:
            Dict[str, Any]: The response JSON from the Ollama API.
        """
        url = f"{self.base_url}/api/chat"
        payload = {
            "model": model,
            "messages": [{"role": "user", "content": message}],
            "stream": False,
        }

        self._add_keep_alive(payload)

        try:
            response = requests.post(url, json=payload)
            response.raise_for_status()  # Raise an HTTPError for bad responses (4xx or 5xx)
            return response.json()
        except requests.RequestException as e:
            print(f"An error occurred while communicating with the Ollama API: {e}")
            return {"error": str(e)}

    def submit_chat_with_history(self, model: str, history: list[Dict[str, Any]], latest_message: str) -> Dict[
        str, Any]:
        """
            Sends a chat history and the latest message to a specific model in the Ollama API.

            Args:
                model (str): The name of the AI model to use (e.g., "llama2").
                history (list): A list of dictionaries representing previous chat messages.
                                Each dictionary should have "role" (e.g., "user" or "assistant")
                                and "content" (message content) keys.
                latest_message (str): The latest user message to include.

            Returns:
                Dict[str, Any]: The response JSON from the Ollama API.
            """
        url = f"{self.base_url}/api/chat"

        # Combine history with the latest message
        messages = history + [{"role": "user", "content": latest_message}]

        payload = {
            "model": model,
            "messages": messages,
            "stream": False,
        }

        self._add_keep_alive(payload)

        try:
            response = requests.post(url, json=payload)
            response.raise_for_status()  # Raise an HTTPError for bad responses (4xx or 5xx)
            return response.json()
        except requests.RequestException as e:
            print(f"An error occurred while communicating with the Ollama API: {e}")
            return {"error": str(e)}

    def submit_generate_request(self, model: str, prompt: str) -> Dict[str, Any]:
        """
            Interacts with the /api/generate endpoint to generate a response for a given prompt
            using a specific model in a non-streaming manner.

            Args:
                model (str): The name of the AI model to use (e.g., "llama2").
                prompt (str): The input prompt for the model.

            Returns:
                Dict[str, Any]: The response JSON from the Ollama API.
            """
        url = f"{self.base_url}/api/generate"
        payload = {
            "model": model,
            "prompt": prompt,
            "stream": False  # Non-streaming response
        }

        self._add_keep_alive(payload)

        try:
            response = requests.post(url, json=payload)
            response.raise_for_status()  # Raise an HTTPError for bad responses (4xx or 5xx)
            return response.json()  # Return the parsed JSON response
        except requests.RequestException as e:
            print(f"An error occurred while interacting with the ollama /api/generate endpoint: {e}")
            return {"error": str(e)}

    def get_model_metadata(self, model: str) -> Dict[str, Any]:
        """
        Retrieves metadata about a specific model from the Ollama API.

        Args:
            model (str): The name of the AI model to query.

        Returns:
            Dict[str, Any]: The metadata response JSON from the Ollama API.
        """
        url = f"{self.base_url}/api/models/{model}"

        try:
            response = requests.get(url)
            response.raise_for_status()
            return response.json()
        except requests.RequestException as e:
            print(f"An error occurred while fetching the model metadata: {e}")
            return {"error": str(e)}

    def list_available_models(self) -> list[Any]:
        """
        Retrieves a list of all available models from the Ollama API.

        Returns:
            Dict[str, Any]: The list of available models as a JSON response.
        """
        url = f"{self.base_url}/api/tags"

        try:
            response = requests.get(url)
            response.raise_for_status()
            raw_response = response.json()

            models = raw_response["models"]

            return sorted(models, key=lambda model: model["name"])

        except requests.RequestException as e:
            print(f"An error occurred while retrieving the model list: {e}")
            raise

    def list_loaded(self) -> Dict[str, Any]:
        """
        Retrieves a list of loaded models

        Returns:
            Dict[str, Any]: The list of loaded models
        """
        url = f"{self.base_url}/api/ps"

        try:
            response = requests.get(url)
            response.raise_for_status()
            return response.json()
        except requests.RequestException as e:
            print(f"An error occurred while retrieving the active model list: {e}")
            return {"error": str(e)}

    def get_version(self) -> str:
        """
            Retrieves the version of the Ollama API.

            Returns:
                str: The version string from the API response (e.g., "0.5.1").
            """
        url = f"{self.base_url}/api/version"

        try:
            response = requests.get(url)
            response.raise_for_status()  # Raise an error for 4xx or 5xx responses
            version_data = response.json()  # Parse the response as JSON
            return version_data.get("version", "Unknown version")  # Safely extract the version
        except requests.RequestException as e:
            print(f"An error occurred while retrieving the version: {e}")
            return "Error retrieving version"

    def download_model(self, model) -> bool:
        """
        Pulls a model for the Ollama API.

        :param model: name of the model to pull
        :return: true if the model was successfully pulled, false otherwise
        """
        url = f"{self.base_url}/api/pull"
        payload = {
            "model": model,
            "stream": False  # Non-streaming response
        }

        try:
            response = requests.post(url, json=payload)
            print(response.content().decode("utf-8"))
            response.raise_for_status()  # Raise an HTTPError for bad responses (4xx or 5xx)
            return response.json()["status"] == "success"  # Return the parsed JSON response
        except requests.RequestException as e:
            print(f"An error occurred while interacting with the ollama pull endpoint: {e}")
            print("Failed to pull model: ", model)
            return False

    def _add_keep_alive(self, payload: Dict[str, Any]):
        if self.unload_delay is not None:
            payload["keep_alive"] = f"{self.unload_delay}s"
