from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field


class TestSessionCreate(BaseModel):
    grade: Literal["junior", "middle", "senior"]


class ConceptSummary(BaseModel):
    id: int
    name: str
    domain: str
    grade: str


class TaskResponse(BaseModel):
    id: int
    concept_id: int
    grade: str
    statement: str
    task_format: str
    options: list
    image_data_url: str | None = None


class TestSessionResponse(BaseModel):
    id: int
    grade: str
    status: str
    task_count: int
    correct_count: int
    result_score: int | None
    verdict: str | None
    expires_at: str | None = None
    tasks: list[TaskResponse]


class TestSessionSummary(BaseModel):
    id: int
    grade: str
    status: str
    task_count: int
    correct_count: int
    result_score: int | None
    verdict: str | None
    created_at: datetime | None = None
    completed_at: datetime | None = None

    class Config:
        from_attributes = True


class TaskAnnotation(BaseModel):
    x: float = Field(ge=0, le=1)
    y: float = Field(ge=0, le=1)
    w: float = Field(ge=0, le=1)
    h: float = Field(ge=0, le=1)


class AnswerSubmit(BaseModel):
    task_id: int
    answer: str | None = Field(default=None, max_length=2000)
    option_index: int | None = None
    annotation: TaskAnnotation | None = None


class AnswerReview(BaseModel):
    task_id: int
    statement: str
    options: list
    selected_index: int | None
    reference_answer: int | None
    is_correct: bool
    task_format: str = "multiple_choice"
    answer_text: str | None = None
    feedback: str | None = None
    image_data_url: str | None = None


class TestSessionResultResponse(BaseModel):
    id: int
    grade: str
    task_count: int
    correct_count: int
    result_score: int
    verdict: str
    suggested_grade: str | None
    grade_applied: bool = False
    review: list[AnswerReview]
