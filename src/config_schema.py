import os
from typing import Literal, Optional

from dotenv import load_dotenv
from pydantic import BaseModel, Field, model_validator

env_path = "config/.env"
load_dotenv(dotenv_path=env_path)


class ServiceConfig(BaseModel):
    name: str
    version: str
    description: Optional[str]


class LoggingConfig(BaseModel):
    level: str
    format: Optional[str]


class LLMConfig(BaseModel):
    provider: str = "gemini"

    default_model: str
    default_temperature: float = Field(ge=0, le=2)
    default_max_tokens: Optional[int]

    api_key: Optional[str] = None

    @model_validator(mode="after")
    def inject_gemini_api_key(self):
        if not self.api_key:
            val = os.getenv("GEMINI_API_KEY")
            if val:
                self.api_key = str(val)

        if not self.api_key:
            raise ValueError(
                "Gemini API key not set. "
                "Please set environment variable GEMINI_API_KEY."
            )

        return self


class PipelineConfig(BaseModel):
    slides_type: Literal["PPT", "3B1B"]


class PPTConfig(BaseModel):
    max_retries: int
    retry_base_delay: float
    max_review_rounds: int
    review_threshold: float


class OutputConfig(BaseModel):
    tmp_dir: Optional[str]
    final_video_dir: Optional[str]


class AppConfig(BaseModel):
    service: ServiceConfig
    logging: LoggingConfig
    llm: LLMConfig
    pipeline: PipelineConfig
    ppt: PPTConfig
    output: Optional[OutputConfig]
