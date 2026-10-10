from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator


HeuristicId = Literal[
    "nielsen_visibility", "nielsen_consistency", "nielsen_error_prevention",
    "nielsen_user_control", "fitts_targets", "contrast", "hierarchy",
]
CriterionId = Literal["evidence", "reasoning", "prioritization", "actionability"]


class AuditInput(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True, extra="forbid")


class DesignerAuditCreate(AuditInput):
    scenario: str = Field(min_length=10, max_length=4000)
    screenshot_data_url: str = Field(min_length=1, max_length=2800000)


class HeuristicChecklistItem(BaseModel):
    id: HeuristicId
    principle: str
    question: str
    evidence_hint: str


class SelectedViolation(AuditInput):
    heuristic_id: HeuristicId
    rationale: str = Field(min_length=10, max_length=2000)
    evidence: str = Field(min_length=5, max_length=1000)
    severity: Literal["low", "medium", "high"]
    recommendation: str = Field(min_length=10, max_length=1000)


class DesignerAuditSubmit(AuditInput):
    violations: list[SelectedViolation] = Field(min_length=1, max_length=7)

    @model_validator(mode="after")
    def unique_heuristics(self):
        ids = [item.heuristic_id for item in self.violations]
        if len(ids) != len(set(ids)):
            raise ValueError("Каждую эвристику можно выбрать только один раз")
        return self


class RubricCriterion(AuditInput):
    id: CriterionId
    score: int = Field(ge=0, le=4, strict=True)
    feedback: str = Field(min_length=1, max_length=1000)


class RubricAssessment(AuditInput):
    criteria: list[RubricCriterion] = Field(min_length=4, max_length=4)
    summary: str = Field(min_length=1, max_length=2000)

    @model_validator(mode="after")
    def complete_rubric(self):
        if {item.id for item in self.criteria} != {"evidence", "reasoning", "prioritization", "actionability"}:
            raise ValueError("Нужны все четыре критерия рубрики")
        return self


class DesignerAuditEvaluation(RubricAssessment):
    score: float = Field(ge=0, le=100)
    source: Literal["llm", "deterministic"]
    evidence_mode: Literal["text_only", "image_and_text"] = "text_only"
    limitation: str
    testing_score: float | None = Field(default=None, ge=0, le=1)
    reference_coverage: float | None = Field(default=None, ge=0, le=1)
    missed_defects: list[str] = Field(default_factory=list)


class DesignerAuditResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    scenario: str
    task_key: str | None
    screenshot_data_url: str
    status: Literal["pending", "submitted"]
    checklist: list[HeuristicChecklistItem]
    violations: list[SelectedViolation]
    evaluation: DesignerAuditEvaluation | None
    created_at: datetime
    submitted_at: datetime | None


class PortfolioMetric(BaseModel):
    metric: str
    value: str
    evidence: str


class PortfolioMetricsResponse(BaseModel):
    metrics: list[PortfolioMetric]
    text_chars: int
    limitation: str
