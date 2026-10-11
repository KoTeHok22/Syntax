from datetime import datetime

from pydantic import BaseModel, Field, model_validator


class RegularTaskCreate(BaseModel):
    vacancy_id: int
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
    vacancy_id: int
    statement: str
    task_format: str
    options: list
    is_active: bool
    created_at: datetime


class RegularTaskSessionResponse(BaseModel):
    id: int
    application_id: int
    vacancy_id: int
    status: str
    task_count: int
    correct_count: int
    result_score: int | None = None
    forced_finish: bool = False
    expires_at: datetime | None = None
    completed_at: datetime | None = None
    tasks: list


class RegularTaskAnswerSubmit(BaseModel):
    regular_task_id: int
    option_index: int = Field(ge=0)


class RegularTaskSessionResult(BaseModel):
    id: int
    status: str
    task_count: int
    correct_count: int
    result_score: int
    forced_finish: bool = False


class ApplicationTaskResult(BaseModel):
    application_id: int
    vacancy_id: int
    status: str
    task_count: int
    correct_count: int
    result_score: int | None = None
    forced_finish: bool = False
    completed_at: datetime | None = None
