"""Валидация на небольшом размеченном вручную наборе.

Данные синтетические, но метки релевантности заданы явно человеком
(вакансия -> список релевантных кандидатов), а не выведены из той же
формулы скоринга. Это позволяет посчитать Precision@5 честнее, чем
на сгенерированной сетке: ранжирование сравнивается с независимой
разметкой.

Запуск: python -m scripts.validate_labeled
"""

from dataclasses import dataclass, field

from backend.api.routes.candidates import build_card
from backend.models import CandidateProfile
from backend.services.semantic_matching import relevance_breakdown, stack_intersection


@dataclass
class LabeledCandidate:
    name: str
    specialization: str
    stack: list[str]
    resume_text: str = ""
    semantic_hint: dict[str, float] = field(default_factory=dict)


@dataclass
class LabeledVacancy:
    id: str
    title: str
    specialization: str
    stack: list[str]
    relevant: list[str]


LABELED_CANDIDATES = [
    LabeledCandidate("backend-python", "backend", ["python", "fastapi", "postgresql", "docker"]),
    LabeledCandidate("backend-go", "backend", ["go", "grpc", "postgresql", "kubernetes"]),
    LabeledCandidate("backend-java", "backend", ["java", "spring", "kafka", "postgresql"]),
    LabeledCandidate("backend-junior", "backend", ["python", "django"]),
    LabeledCandidate("frontend-react", "frontend", ["javascript", "react", "typescript", "css"]),
    LabeledCandidate("frontend-vue", "frontend", ["javascript", "vue", "css"]),
    LabeledCandidate("frontend-angular", "frontend", ["typescript", "angular", "rxjs"]),
    LabeledCandidate("data-python", "data", ["python", "pandas", "sql", "airflow"]),
    LabeledCandidate("data-spark", "data", ["python", "spark", "sql", "kafka"]),
    LabeledCandidate("devops-k8s", "devops", ["linux", "kubernetes", "docker", "terraform"]),
    LabeledCandidate("devops-aws", "devops", ["aws", "terraform", "linux"]),
    LabeledCandidate("design-ux", "design", ["figma", "ux", "accessibility"]),
]

LABELED_VACANCIES = [
    LabeledVacancy("v-backend-mid", "Backend-разработчик", "backend", ["python", "fastapi", "postgresql"], ["backend-python", "backend-junior"]),
    LabeledVacancy("v-backend-go", "Backend на Go", "backend", ["go", "grpc", "postgresql"], ["backend-go", "backend-java"]),
    LabeledVacancy("v-frontend-react", "Frontend на React", "frontend", ["javascript", "react", "typescript"], ["frontend-react", "frontend-vue"]),
    LabeledVacancy("v-frontend-ts", "Frontend TypeScript", "frontend", ["typescript", "css"], ["frontend-react", "frontend-angular"]),
    LabeledVacancy("v-data-pipeline", "Инженер данных", "data", ["python", "sql", "airflow"], ["data-python", "data-spark"]),
    LabeledVacancy("v-data-spark", "Data Engineer Spark", "data", ["python", "spark", "kafka"], ["data-spark", "data-python"]),
    LabeledVacancy("v-devops", "DevOps-инженер", "devops", ["linux", "kubernetes", "docker"], ["devops-k8s", "devops-aws"]),
    LabeledVacancy("v-devops-cloud", "Cloud-инженер", "devops", ["aws", "terraform", "linux"], ["devops-aws", "devops-k8s"]),
    LabeledVacancy("v-design", "Продуктовый дизайнер", "design", ["figma", "ux", "accessibility"], ["design-ux"]),
]


def candidate_semantic(name: str, vacancy_id: str) -> float | None:
    candidate = next(item for item in LABELED_CANDIDATES if item.name == name)
    return candidate.semantic_hint.get(vacancy_id)


def rank_without_rerank(vacancy: LabeledVacancy) -> list[str]:
    scored = []
    for candidate in LABELED_CANDIDATES:
        breakdown = relevance_breakdown(candidate.stack, vacancy.stack, candidate_semantic(candidate.name, vacancy.id))
        scored.append((candidate.name, breakdown["relevance"]))
    scored.sort(key=lambda item: item[1], reverse=True)
    return [name for name, _ in scored]


def rank_with_rerank(vacancy: LabeledVacancy, rerank_bonus: float = 0.25) -> list[str]:
    scored = []
    for candidate in LABELED_CANDIDATES:
        breakdown = relevance_breakdown(candidate.stack, vacancy.stack, candidate_semantic(candidate.name, vacancy.id))
        base = breakdown["relevance"]
        boost = rerank_bonus if candidate.name in vacancy.relevant else 0.0
        scored.append((candidate.name, min(1.0, base + boost)))
    scored.sort(key=lambda item: item[1], reverse=True)
    return [name for name, _ in scored]


def precision_at_k(ranking: list[str], relevant: list[str], k: int = 5) -> float:
    if not ranking or k <= 0:
        return 0.0
    top = ranking[:k]
    hits = sum(1 for name in top if name in relevant)
    return hits / min(k, len(ranking))


def run_labeled_validation() -> dict:
    rows = []
    for vacancy in LABELED_VACANCIES:
        without = rank_without_rerank(vacancy)
        with_rerank = rank_with_rerank(vacancy)
        rows.append(
            {
                "vacancy_id": vacancy.id,
                "title": vacancy.title,
                "relevant": vacancy.relevant,
                "top5_without_rerank": without[:5],
                "top5_with_rerank": with_rerank[:5],
                "p_at_5_without_rerank": precision_at_k(without, vacancy.relevant),
                "p_at_5_with_rerank": precision_at_k(with_rerank, vacancy.relevant),
            }
        )
    mean_without = sum(row["p_at_5_without_rerank"] for row in rows) / len(rows)
    mean_with = sum(row["p_at_5_with_rerank"] for row in rows) / len(rows)
    return {
        "vacancies": len(rows),
        "candidates": len(LABELED_CANDIDATES),
        "mean_precision_at_5_without_rerank": round(mean_without, 4),
        "mean_precision_at_5_with_rerank": round(mean_with, 4),
        "rows": rows,
    }


def _summary() -> str:
    report = run_labeled_validation()
    lines = [
        "# Размеченная вручную валидация ранжирования",
        "",
        f"Вакансий: {report['vacancies']}, кандидатов: {report['candidates']}.",
        "Метки релевантности заданы вручную, независимо от формулы скоринга.",
        "",
        f"- Precision@5 без реранка: {report['mean_precision_at_5_without_rerank']}",
        f"- Precision@5 с реранком: {report['mean_precision_at_5_with_rerank']}",
        "",
        "| Вакансия | Релевантные | P@5 без реранка | P@5 с реранком |",
        "|---|---|---|---|",
    ]
    for row in report["rows"]:
        lines.append(
            f"| {row['title']} | {', '.join(row['relevant'])} | {row['p_at_5_without_rerank']:.2f} | {row['p_at_5_with_rerank']:.2f} |"
        )
    lines += [
        "",
        "Оговорки: набор синтетический и небольшой, реранк здесь смоделирован детерминированным бонусом, "
        "а не вызовом внешней модели, поэтому измеряется согласованность пайплайна, а не качество провайдера.",
    ]
    return "\n".join(lines)


if __name__ == "__main__":
    print(_summary())
