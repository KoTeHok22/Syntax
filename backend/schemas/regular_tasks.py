from datetime import datetime

from pydantic import BaseModel, Field, model_validator


class RegularTaskCreate(BaseModel):
    concept_id: int | None = None
    statement: str | None = Field(default=None, max_length=4000)
    options: list[str] | None = None
    correct_index: int | None = None

    @model_validator(mode="after")
    def check_source(self):
        if self.concept_id is not None:
            return self
        if not self.statement or not self.options or self.correct_index is None:
            raise ValueError("Укажите concept_id либо statement, options и correct_index")
        if len(self.options) < 2:
            raise ValueError("Нужно минимум два варианта ответа")
        if not 0 <= self.correct_index < len(self.options):
            raise ValueError("correct_index вне диапазона вариантов")
        return self


class RegularTaskResponse(BaseModel):
    id: int
    statement: str
    task_format: str
    options: list
    is_active: bool
    created_at: datetime


class RegularTaskAnswer(BaseModel):
    option_index: int = Field(ge=0)


class RegularTaskAnswerResponse(BaseModel):
    regular_task_id: int
    is_correct: bool


class RegularTaskSubmissionResponse(BaseModel):
    id: int
    regular_task_id: int
    candidate_profile_id: int
    is_correct: bool
    submitted_at: datetime
