from pydantic import BaseModel


class ConfigModel(BaseModel):
    selected_model: str
    correction_re_runs: int
    auto_summaries: bool


default_config = ConfigModel(
    selected_model="deepseek-r1:32b",
    correction_re_runs=2,
    auto_summaries=True)
