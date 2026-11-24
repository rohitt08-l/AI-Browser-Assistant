"""Request / response schemas for the public API."""

from enum import StrEnum
from typing import Literal

from pydantic import BaseModel, Field, field_validator, model_validator


class TaskType(StrEnum):
    AUTO = "auto"
    QA = "qa"
    SUMMARIZE = "summarize"
    NOTES = "notes"
    GENERATE_DOC = "generate_doc"


class ChatMessage(BaseModel):
    role: Literal["user", "assistant"]
    content: str = Field(max_length=20_000)


class AskRequest(BaseModel):
    question: str = Field(default="", max_length=4_000)
    page_content: str = Field(min_length=1)
    page_title: str = Field(default="", max_length=500)
    page_url: str = Field(default="", max_length=2_000)
    selection: str = Field(default="", max_length=20_000)
    task_type: TaskType = TaskType.AUTO
    history: list[ChatMessage] = Field(default_factory=list, max_length=50)

    @field_validator("task_type", mode="before")
    @classmethod
    def _normalise_task(cls, value: object) -> object:
        # Accept "QA", " Summarize ", "generate-doc", ...
        if isinstance(value, str):
            return value.strip().lower().replace("-", "_").replace(" ", "_")
        return value

    @field_validator("question", "page_content", "selection", mode="after")
    @classmethod
    def _strip(cls, value: str) -> str:
        return value.strip()

    @model_validator(mode="after")
    def _question_required_for_qa(self) -> "AskRequest":
        if not self.page_content:
            raise ValueError("The page has no readable text")
        if self.task_type in (TaskType.QA, TaskType.AUTO) and not self.question:
            raise ValueError("A question is required for Q&A / auto mode")
        return self


class AskResponse(BaseModel):
    answer: str
    task: TaskType
    file_url: str | None = None
