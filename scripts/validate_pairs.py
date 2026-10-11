import math
import sys
from dataclasses import dataclass, field
from datetime import date
from pathlib import Path
from types import SimpleNamespace

from backend.api.routes.candidates import build_card
from backend.core.scoring import RankableCandidate, ranking_key
from backend.core.testing import result_score
from backend.models import PvnAchievement, TestSession

SEED = 42
TASKS_PER_SESSION = 5
K = 5
GRADE_LABELS = {0: "irrelevant", 1: "partially_relevant", 2: "relevant"}


@dataclass
class PairCandidate:
    name: str
    stack: list[str]
    grade_label: int
    years: int = 3
    specialization: str = ""
    grade: str = "middle"
    completed: bool = True
    correct_count: int = 5
    pvn_score: float | None = None
    semantic_hint: dict[str, float] = field(default_factory=dict)


GATE_STRESS_SUFFIX = "-claimed-strong"


def gate_stress_candidate(vacancy_id: str, stack: list[str], specialization: str, grade: str) -> PairCandidate:
    return PairCandidate(
        name=vacancy_id + GATE_STRESS_SUFFIX,
        stack=list(stack),
        grade_label=1,
        years=1,
        specialization=specialization,
        grade=grade,
        completed=False,
        correct_count=0,
        pvn_score=None,
        semantic_hint={vacancy_id: 0.97},
    )


@dataclass
class PairVacancy:
    id: str
    title: str
    specialization: str
    grade: str
    stack: list[str]
    candidates: list[PairCandidate]


PAIR_VACANCIES = [
    PairVacancy(
        "v-backend-python",
        "Backend Python",
        "backend",
        "middle",
        ["python", "fastapi", "postgresql"],
        [
            PairCandidate("python-strong-2", ["python", "fastapi", "postgresql", "redis"], 2, 6, "backend", "middle", True, 5, None, {"v-backend-python": 0.9}),
            PairCandidate("python-strong", ["python", "fastapi", "postgresql", "docker"], 2, 5, "backend", "middle", True, 5, None, {"v-backend-python": 0.92}),
            PairCandidate("python-partial", ["python", "flask", "sqlite"], 1, 3, "backend", "middle", True, 4, None, {"v-backend-python": 0.66}),
            PairCandidate("go-strong", ["go", "grpc", "postgresql"], 1, 5, "backend", "middle", True, 4, None, {"v-backend-python": 0.48}),
            gate_stress_candidate("v-backend-python", ["python", "fastapi", "postgresql"], "backend", "middle"),
            PairCandidate("frontend-mismatch", ["javascript", "react", "typescript"], 0, 3, "frontend", "middle", True, 3, None, {"v-backend-python": 0.12}),
            PairCandidate("backend-manager", ["python", "sql", "team lead"], 0, 9, "backend", "senior", True, 3, 100.0, {"v-backend-python": 0.3}),
        ],
    ),
    PairVacancy(
        "v-backend-go",
        "Backend Go",
        "backend",
        "senior",
        ["go", "grpc", "postgresql"],
        [
            PairCandidate("go-senior-2", ["go", "grpc", "postgresql", "docker"], 2, 6, "backend", "senior", True, 5, None, {"v-backend-go": 0.91}),
            PairCandidate("go-senior", ["go", "grpc", "postgresql", "kubernetes"], 2, 7, "backend", "senior", True, 5, None, {"v-backend-go": 0.94}),
            PairCandidate("go-mid", ["go", "grpc", "mysql"], 1, 4, "backend", "middle", True, 4, None, {"v-backend-go": 0.62}),
            PairCandidate("java-senior", ["java", "spring", "postgresql"], 1, 8, "backend", "senior", True, 4, None, {"v-backend-go": 0.4}),
            gate_stress_candidate("v-backend-go", ["go", "grpc", "postgresql"], "backend", "senior"),
            PairCandidate("data-mismatch", ["python", "spark", "sql"], 0, 5, "data", "senior", True, 3, None, {"v-backend-go": 0.1}),
        ],
    ),
    PairVacancy(
        "v-frontend-react",
        "Frontend React",
        "frontend",
        "middle",
        ["javascript", "react", "typescript"],
        [
            PairCandidate("react-strong-2", ["javascript", "react", "typescript", "redux"], 2, 6, "frontend", "middle", True, 5, None, {"v-frontend-react": 0.91}),
            PairCandidate("react-strong", ["javascript", "react", "typescript", "css"], 2, 5, "frontend", "middle", True, 5, None, {"v-frontend-react": 0.93}),
            PairCandidate("react-partial", ["javascript", "react"], 1, 3, "frontend", "middle", True, 4, None, {"v-frontend-react": 0.7}),
            PairCandidate("vue-strong", ["javascript", "vue", "css"], 1, 5, "frontend", "middle", True, 4, None, {"v-frontend-react": 0.45}),
            gate_stress_candidate("v-frontend-react", ["javascript", "react", "typescript"], "frontend", "middle"),
            PairCandidate("backend-mismatch", ["python", "fastapi", "postgresql"], 0, 4, "backend", "middle", True, 3, None, {"v-frontend-react": 0.08}),
            PairCandidate("design-mismatch", ["figma", "ux", "accessibility"], 0, 3, "design", "middle", True, 3, None, {"v-frontend-react": 0.15}),
        ],
    ),
    PairVacancy(
        "v-frontend-ts",
        "Frontend TypeScript",
        "frontend",
        "senior",
        ["typescript", "css"],
        [
            PairCandidate("ts-senior-2", ["typescript", "css", "next"], 2, 6, "frontend", "senior", True, 5, None, {"v-frontend-ts": 0.88}),
            PairCandidate("ts-senior", ["typescript", "css", "react", "node"], 2, 7, "frontend", "senior", True, 5, None, {"v-frontend-ts": 0.9}),
            PairCandidate("ts-mid", ["typescript", "css"], 1, 4, "frontend", "middle", True, 4, None, {"v-frontend-ts": 0.7}),
            PairCandidate("js-only", ["javascript", "html", "css"], 1, 5, "frontend", "senior", True, 4, None, {"v-frontend-ts": 0.55}),
            gate_stress_candidate("v-frontend-ts", ["typescript", "css"], "frontend", "senior"),
            PairCandidate("backend-mismatch", ["go", "grpc", "postgresql"], 0, 6, "backend", "senior", True, 3, None, {"v-frontend-ts": 0.06}),
        ],
    ),
    PairVacancy(
        "v-data-pipeline",
        "Data Engineer",
        "data",
        "middle",
        ["python", "sql", "airflow"],
        [
            PairCandidate("de-strong-2", ["python", "sql", "airflow", "dbt"], 2, 6, "data", "middle", True, 5, None, {"v-data-pipeline": 0.9}),
            PairCandidate("de-strong", ["python", "sql", "airflow", "spark"], 2, 5, "data", "middle", True, 5, None, {"v-data-pipeline": 0.92}),
            PairCandidate("de-partial", ["python", "sql", "pandas"], 1, 3, "data", "middle", True, 4, None, {"v-data-pipeline": 0.68}),
            PairCandidate("analyst", ["sql", "excel", "tableau"], 1, 4, "data", "middle", True, 4, None, {"v-data-pipeline": 0.5}),
            gate_stress_candidate("v-data-pipeline", ["python", "sql", "airflow"], "data", "middle"),
            PairCandidate("frontend-mismatch", ["javascript", "react", "css"], 0, 3, "frontend", "middle", True, 3, None, {"v-data-pipeline": 0.09}),
        ],
    ),
    PairVacancy(
        "v-data-spark",
        "Data Engineer Spark",
        "data",
        "senior",
        ["python", "spark", "kafka"],
        [
            PairCandidate("spark-strong-2", ["python", "spark", "kafka", "hive"], 2, 6, "data", "senior", True, 5, None, {"v-data-spark": 0.92}),
            PairCandidate("spark-strong", ["python", "spark", "kafka", "scala"], 2, 7, "data", "senior", True, 5, None, {"v-data-spark": 0.95}),
            PairCandidate("spark-mid", ["python", "spark", "sql"], 1, 4, "data", "middle", True, 4, None, {"v-data-spark": 0.66}),
            PairCandidate("kafka-mid", ["java", "kafka", "postgresql"], 1, 5, "data", "senior", True, 4, None, {"v-data-spark": 0.44}),
            gate_stress_candidate("v-data-spark", ["python", "spark", "kafka"], "data", "senior"),
            PairCandidate("backend-mismatch", ["python", "fastapi", "postgresql"], 0, 5, "backend", "senior", True, 3, None, {"v-data-spark": 0.2}),
        ],
    ),
    PairVacancy(
        "v-devops-k8s",
        "DevOps Engineer",
        "devops",
        "middle",
        ["linux", "kubernetes", "docker"],
        [
            PairCandidate("devops-strong-2", ["linux", "kubernetes", "docker", "helm"], 2, 6, "devops", "middle", True, 5, None, {"v-devops-k8s": 0.91}),
            PairCandidate("devops-strong", ["linux", "kubernetes", "docker", "terraform"], 2, 5, "devops", "middle", True, 5, None, {"v-devops-k8s": 0.93}),
            PairCandidate("devops-partial", ["linux", "docker"], 1, 3, "devops", "middle", True, 4, None, {"v-devops-k8s": 0.7}),
            PairCandidate("sre-mid", ["linux", "kubernetes", "prometheus"], 1, 4, "devops", "middle", True, 4, None, {"v-devops-k8s": 0.66}),
            gate_stress_candidate("v-devops-k8s", ["linux", "kubernetes", "docker"], "devops", "middle"),
            PairCandidate("backend-mismatch", ["python", "fastapi", "postgresql"], 0, 4, "backend", "middle", True, 3, None, {"v-devops-k8s": 0.1}),
        ],
    ),
    PairVacancy(
        "v-devops-cloud",
        "Cloud Engineer",
        "devops",
        "senior",
        ["aws", "terraform", "linux"],
        [
            PairCandidate("cloud-strong-2", ["aws", "terraform", "linux", "eks"], 2, 6, "devops", "senior", True, 5, None, {"v-devops-cloud": 0.9}),
            PairCandidate("cloud-strong", ["aws", "terraform", "linux", "kubernetes"], 2, 7, "devops", "senior", True, 5, None, {"v-devops-cloud": 0.91}),
            PairCandidate("cloud-mid", ["aws", "terraform"], 1, 4, "devops", "middle", True, 4, None, {"v-devops-cloud": 0.68}),
            PairCandidate("azure-mid", ["azure", "terraform", "linux"], 1, 5, "devops", "senior", True, 4, None, {"v-devops-cloud": 0.6}),
            gate_stress_candidate("v-devops-cloud", ["aws", "terraform", "linux"], "devops", "senior"),
            PairCandidate("frontend-mismatch", ["javascript", "react", "css"], 0, 3, "frontend", "senior", True, 3, None, {"v-devops-cloud": 0.05}),
        ],
    ),
    PairVacancy(
        "v-mobile-android",
        "Android Developer",
        "mobile",
        "middle",
        ["kotlin", "android", "jetpack compose"],
        [
            PairCandidate("android-strong-2", ["kotlin", "android", "jetpack compose", "room"], 2, 6, "mobile", "middle", True, 5, None, {"v-mobile-android": 0.9}),
            PairCandidate("android-strong", ["kotlin", "android", "jetpack compose", "coroutines"], 2, 5, "mobile", "middle", True, 5, None, {"v-mobile-android": 0.92}),
            PairCandidate("android-partial", ["kotlin", "android"], 1, 3, "mobile", "middle", True, 4, None, {"v-mobile-android": 0.7}),
            PairCandidate("java-android", ["java", "android", "gradle"], 1, 5, "mobile", "middle", True, 4, None, {"v-mobile-android": 0.55}),
            gate_stress_candidate("v-mobile-android", ["kotlin", "android", "jetpack compose"], "mobile", "middle"),
            PairCandidate("backend-mismatch", ["python", "fastapi", "postgresql"], 0, 4, "backend", "middle", True, 3, None, {"v-mobile-android": 0.07}),
        ],
    ),
    PairVacancy(
        "v-qa-automation",
        "QA Automation",
        "qa",
        "middle",
        ["python", "pytest", "selenium"],
        [
            PairCandidate("qa-strong-2", ["python", "pytest", "selenium", "playwright"], 2, 6, "qa", "middle", True, 5, None, {"v-qa-automation": 0.89}),
            PairCandidate("qa-strong", ["python", "pytest", "selenium", "docker"], 2, 5, "qa", "middle", True, 5, None, {"v-qa-automation": 0.9}),
            PairCandidate("qa-partial", ["python", "unittest"], 1, 3, "qa", "middle", True, 4, None, {"v-qa-automation": 0.6}),
            PairCandidate("manual-qa", ["jira", "test cases", "sql"], 1, 5, "qa", "middle", True, 4, None, {"v-qa-automation": 0.35}),
            gate_stress_candidate("v-qa-automation", ["python", "pytest", "selenium"], "qa", "middle"),
            PairCandidate("backend-mismatch", ["go", "grpc", "postgresql"], 0, 4, "backend", "middle", True, 3, None, {"v-qa-automation": 0.08}),
        ],
    ),
    PairVacancy(
        "v-ml-engineer",
        "ML Engineer",
        "data",
        "senior",
        ["python", "pytorch", "mlops"],
        [
            PairCandidate("ml-strong-2", ["python", "pytorch", "mlops", "airflow"], 2, 6, "data", "senior", True, 5, None, {"v-ml-engineer": 0.92}),
            PairCandidate("ml-strong", ["python", "pytorch", "mlops", "docker"], 2, 7, "data", "senior", True, 5, None, {"v-ml-engineer": 0.94}),
            PairCandidate("ml-partial", ["python", "pytorch", "pandas"], 1, 4, "data", "middle", True, 4, None, {"v-ml-engineer": 0.7}),
            PairCandidate("datascience", ["python", "sklearn", "sql"], 1, 5, "data", "senior", True, 4, None, {"v-ml-engineer": 0.58}),
            gate_stress_candidate("v-ml-engineer", ["python", "pytorch", "mlops"], "data", "senior"),
            PairCandidate("frontend-mismatch", ["javascript", "react", "css"], 0, 3, "frontend", "senior", True, 3, None, {"v-ml-engineer": 0.06}),
        ],
    ),
    PairVacancy(
        "v-product-design",
        "Product Designer",
        "design",
        "middle",
        ["figma", "ux", "prototyping"],
        [
            PairCandidate("design-strong-2", ["figma", "ux", "prototyping", "design system"], 2, 6, "design", "middle", True, 5, None, {"v-product-design": 0.89}),
            PairCandidate("design-strong", ["figma", "ux", "prototyping", "accessibility"], 2, 5, "design", "middle", True, 5, None, {"v-product-design": 0.9}),
            PairCandidate("design-partial", ["figma", "ui"], 1, 3, "design", "middle", True, 4, None, {"v-product-design": 0.65}),
            PairCandidate("graphic-designer", ["photoshop", "illustrator", "figma"], 1, 5, "design", "middle", True, 4, None, {"v-product-design": 0.5}),
            gate_stress_candidate("v-product-design", ["figma", "ux", "prototyping"], "design", "middle"),
            PairCandidate("frontend-mismatch", ["javascript", "react", "css"], 0, 4, "frontend", "middle", True, 3, None, {"v-product-design": 0.2}),
        ],
    ),
]


class MemoryQuery:
    def __init__(self, rows):
        self.rows = rows

    def filter(self, *conditions):
        return self

    def order_by(self, *ordering):
        return self

    def all(self):
        return self.rows

    def first(self):
        return self.rows[0] if self.rows else None


class MemorySession:
    def __init__(self, candidate):
        self.candidate = candidate
        self.bind = SimpleNamespace(dialect=SimpleNamespace(name="sqlite"))

    def query(self, model):
        rows = {
            TestSession: self.candidate.sessions,
            PvnAchievement: self.candidate.achievements,
        }
        return MemoryQuery(rows.get(model, []))

    def flush(self):
        return None


def candidate_fixture(vacancy: PairVacancy, spec: PairCandidate, candidate_id: int):
    sessions = []
    if spec.completed:
        sessions = [SimpleNamespace(result_score=result_score(spec.correct_count, TASKS_PER_SESSION))]
    achievements = []
    if spec.pvn_score is not None:
        achievements = [
            SimpleNamespace(score=spec.pvn_score, achievement_type="synthetic", level="mock", achieved_at=date(2026, 1, 1))
        ]
    return SimpleNamespace(
        id=candidate_id,
        full_name=spec.name,
        contacts={"email": f"{spec.name}@example.test"},
        stack=list(spec.stack),
        specialization=spec.specialization,
        grade=spec.grade,
        years_of_experience=spec.years,
        soft_skills=["communication"],
        category_id=1,
        resume_text=f"semantic hint for {spec.name}",
        assessment_text="mock practical result",
        portfolio_evidence={},
        embedding=None,
        embedding_text=None,
        embedding_model=None,
        sessions=sessions,
        achievements=achievements,
    )


def build_cards(vacancy: PairVacancy, mode: str) -> list[dict]:
    cards = []
    for offset, spec in enumerate(vacancy.candidates):
        candidate = candidate_fixture(vacancy, spec, hash((vacancy.id, spec.name)) & 0xFFFFFFF)
        similarity = spec.semantic_hint.get(vacancy.id) if mode == "semantic" else None
        card = build_card(MemorySession(candidate), candidate, vacancy.stack, similarity)
        cards.append(
            {
                "name": spec.name,
                "grade_label": spec.grade_label,
                "card": card,
                "rankable": RankableCandidate(
                    final_score=card.final_score,
                    score=card.score,
                    proof_tier="verified" if spec.completed else "claimed",
                ),
            }
        )
    return cards


def relevance_grades(cards: list[dict]) -> dict[str, int]:
    return {item["name"]: item["grade_label"] for item in cards}


def rank(cards: list[dict], gate: bool) -> list[str]:
    if gate:
        ordered = sorted(
            cards,
            key=lambda item: ranking_key(
                item["rankable"].final_score,
                item["rankable"].score,
                proof_tier_value=item["rankable"].proof_tier,
            ),
            reverse=True,
        )
    else:
        ordered = sorted(cards, key=lambda item: (item["card"].final_score, item["card"].score), reverse=True)
    return [item["name"] for item in ordered]


def precision_at_k(ranking: list[str], grades: dict[str, int], k: int, threshold: int = 2) -> float:
    top = ranking[:k]
    if not top:
        return 0.0
    hits = sum(1 for name in top if grades.get(name, 0) >= threshold)
    return hits / len(top)


def recall_at_k(ranking: list[str], grades: dict[str, int], k: int, threshold: int = 2) -> float:
    relevant = [name for name, grade in grades.items() if grade >= threshold]
    if not relevant:
        return 0.0
    top = set(ranking[:k])
    return sum(1 for name in relevant if name in top) / len(relevant)


def dcg(gains: list[float]) -> float:
    return sum(gain / math.log2(index + 2) for index, gain in enumerate(gains))


def ndcg_at_k(ranking: list[str], grades: dict[str, int], k: int, threshold: int = 2) -> float:
    gains = [1.0 if grades.get(name, 0) >= threshold else 0.0 for name in ranking[:k]]
    ideal = sorted((1.0 if grade >= threshold else 0.0 for grade in grades.values()), reverse=True)[:k]
    ideal_dcg = dcg(ideal)
    if ideal_dcg == 0.0:
        return 0.0
    return dcg(gains) / ideal_dcg


def reciprocal_rank(ranking: list[str], grades: dict[str, int], threshold: int = 2) -> float:
    for index, name in enumerate(ranking, start=1):
        if grades.get(name, 0) >= threshold:
            return 1.0 / index
    return 0.0


def evaluate(mode: str, gate: bool) -> dict:
    rows = []
    for vacancy in PAIR_VACANCIES:
        cards = build_cards(vacancy, mode)
        grades = relevance_grades(cards)
        ranking = rank(cards, gate)
        rows.append(
            {
                "vacancy_id": vacancy.id,
                "title": vacancy.title,
                "ranking": ranking,
                "precision_at_5": precision_at_k(ranking, grades, K),
                "recall_at_10": recall_at_k(ranking, grades, 10),
                "ndcg_at_5": ndcg_at_k(ranking, grades, K),
                "reciprocal_rank": reciprocal_rank(ranking, grades),
            }
        )
    count = len(rows)
    return {
        "mode": mode,
        "gate": gate,
        "vacancies": count,
        "precision_at_5": round(sum(row["precision_at_5"] for row in rows) / count, 4),
        "recall_at_10": round(sum(row["recall_at_10"] for row in rows) / count, 4),
        "ndcg_at_5": round(sum(row["ndcg_at_5"] for row in rows) / count, 4),
        "mrr": round(sum(row["reciprocal_rank"] for row in rows) / count, 4),
        "rows": rows,
    }


def embedding_available() -> bool:
    from backend.core.config import get_settings

    return bool(get_settings().embeddings_enabled)


def run_validation() -> dict:
    modes = ["lexical"]
    if embedding_available():
        modes.append("semantic")
    results = {(mode, gate): evaluate(mode, gate) for mode in modes for gate in (False, True)}
    return {
        "seed": SEED,
        "modes": modes,
        "semantic_note": None if "semantic" in modes else "semantic mode skipped: embeddings_enabled is false in this environment",
        "results": results,
    }


def _row_index(results: dict) -> dict:
    return {key: result for key, result in results["results"].items()}


def render_report(results: dict) -> str:
    index = _row_index(results)
    lines = [
        "# Бенчмарк ранжирования на размеченном наборе пар «вакансия–кандидат»",
        "",
        "Воспроизводимый offline-бенчмарк: ранжирование считается реальным backend `build_card`, "
        "метрики — по ручной разметке релевантности, независимой от формулы скоринга.",
        "Набор синтетический (командная разметка на синтетике, не экспертная). Критерии — в `docs/pairs-dataset.md`.",
        "",
        "## Состав набора",
        f"- Вакансий: {len(PAIR_VACANCIES)}, кандидатов: {sum(len(v.candidates) for v in PAIR_VACANCIES)}.",
        f"- Метрики: Precision@{K}, NDCG@{K}, MRR, Recall@10; порог релевантности — grade≥2.",
        "",
        "## Метрики",
        "| Режим | Hard-gate | Precision@5 | NDCG@5 | MRR | Recall@10 |",
        "|---|---|---|---|---|---|",
    ]
    for mode in results["modes"]:
        for gate in (False, True):
            result = index[(mode, gate)]
            label = "с gate" if gate else "без gate"
            lines.append(
                f"| {mode} | {label} | {result['precision_at_5']:.3f} | {result['ndcg_at_5']:.3f} | "
                f"{result['mrr']:.3f} | {result['recall_at_10']:.3f} |"
            )
    lines.append("")
    lines.append("## Дельта от hard-gate")
    for mode in results["modes"]:
        before = index[(mode, False)]
        after = index[(mode, True)]
        lines.append(
            f"- {mode}: Precision@5 {before['precision_at_5']:.3f} → {after['precision_at_5']:.3f} "
            f"({after['precision_at_5'] - before['precision_at_5']:+.3f}), "
            f"NDCG@5 {before['ndcg_at_5']:.3f} → {after['ndcg_at_5']:.3f} "
            f"({after['ndcg_at_5'] - before['ndcg_at_5']:+.3f}), "
            f"MRR {before['mrr']:.3f} → {after['mrr']:.3f} "
            f"({after['mrr'] - before['mrr']:+.3f})."
        )
    lines.append("")
    lines.append("## Ранжирование по вакансиям (gate=on)")
    lines.append("| Вакансия | P@5 | NDCG@5 | MRR | Top-5 |")
    lines.append("|---|---|---|---|---|")
    for mode in results["modes"]:
        if mode != results["modes"][0]:
            continue
        for row in index[(mode, True)]["rows"]:
            lines.append(
                f"| {row['title']} | {row['precision_at_5']:.2f} | {row['ndcg_at_5']:.2f} | "
                f"{row['reciprocal_rank']:.2f} | {', '.join(row['ranking'][:5])} |"
            )
    lines.append("")
    if results["semantic_note"]:
        lines.append(f"Примечание: {results['semantic_note']}.")
        lines.append("")
    lines.append("## Ограничения")
    lines.append(
        "Разметка — командная и выполнена на синтетических профилях, а не экспертами на реальных резюме. "
        "Набор небольшой (12 вакансий), профили внутри вакансии пересекаются по стеку, поэтому метрики "
        "нельзя трактовать как рыночное качество подбора. Hard-gate по тиру (verified/claimed) меняет порядок "
        "только там, где рядом стоят профили разных тиров; его эффект измерен и приведён выше, включая случаи, "
        "где он не помогает или ухудшает порядок."
    )
    lines.append("")
    lines.append("## Воспроизведение")
    lines.append("`python -m scripts.validate_pairs` перезаписывает этот отчёт; `python -m pytest tests/test_pairs_validation.py -q`.")
    return "\n".join(lines)


def main() -> None:
    report = render_report(run_validation())
    Path(__file__).resolve().parents[1].joinpath("docs", "pairs-results.md").write_text(report, encoding="utf-8")
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    print(report)


if __name__ == "__main__":
    main()
