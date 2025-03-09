from typing import Optional

from pydantic import BaseModel

DEFAULT_MODEL = "deepseek-r1:32b"

# Depends on model context / how big the model is that how much text it can take before it writes something not about
# the prompt, so these need to be tuned pretty low for deepseek local models
DEFAULT_EXCERPT_LENGTH = 6200
DEFAULT_SIMULTANEOUS_CORRECTION_SIZE = 500

DEFAULT_AI_UNLOAD_DELAY = 75


# We have to use camelCase here to be compatible with the frontend
class ConfigModel(BaseModel):
    selectedModel: str
    correctionReRuns: int
    autoSummaries: bool
    styleExcerptLength: int = DEFAULT_EXCERPT_LENGTH
    simultaneousCorrectionSize: int = DEFAULT_SIMULTANEOUS_CORRECTION_SIZE
    unusedAIUnloadDelay: int = DEFAULT_AI_UNLOAD_DELAY
    customOllamaUrl: Optional[str] = None


default_config = ConfigModel(
    selectedModel=DEFAULT_MODEL,
    correctionReRuns=2,
    autoSummaries=True,
    styleExcerptLength=DEFAULT_EXCERPT_LENGTH,
    simultaneousCorrectionSize=DEFAULT_SIMULTANEOUS_CORRECTION_SIZE,
    unusedAIUnloadDelay=DEFAULT_AI_UNLOAD_DELAY)
