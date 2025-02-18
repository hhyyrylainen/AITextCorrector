from pydantic import BaseModel


# We have to use camelCase here to be compatible with the frontend
class ConfigModel(BaseModel):
    selectedModel: str
    correctionReRuns: int
    autoSummaries: bool


default_config = ConfigModel(
    selectedModel="deepseek-r1:32b",
    correctionReRuns=2,
    autoSummaries=True)
