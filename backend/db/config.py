from pydantic import BaseModel

DEFAULT_MODEL = "deepseek-r1:32b"

# We have to use camelCase here to be compatible with the frontend
class ConfigModel(BaseModel):
    selectedModel: str
    correctionReRuns: int
    autoSummaries: bool


default_config = ConfigModel(
    selectedModel=DEFAULT_MODEL,
    correctionReRuns=2,
    autoSummaries=True)
