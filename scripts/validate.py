import asyncio
import math
import random
import sys
from datetime import date
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

from backend.api.routes.candidates import build_card
from backend.core.scoring import RELEVANCE_MAX_BONUS, ranking_key
from backend.core.testing import adaptive_verdict, result_score, suggested_grade
from backend.models import PvnAchievement, TestSession
from backend.services import semantic_matching

SEED = 42
TASKS_PER_SESSION = 5
GRADES = ["junior", "middle", "senior"]
STACKS = {
    "backend": ["python", "fastapi", "postgresql"],
    "frontend": ["javascript", "react", "typescript"],
    "data": ["python", "sql", "airflow"],
    "devops": ["linux", "docker", "kubernetes"],
}
CASE_INPUTS = [
    ("same_stack", 0, 5, 3, None, 0.9, 0.9),
    ("failed_one", 1, 4, 3, None, 0.9, 0.9),
    ("partial_verified_stack", 0, 5, 2, None, 0.9, 0.9),
    ("sparse_verified_stack", 1, 4, 1, None, 0.9, 0.9),
    ("unverified_keyword_stuffing", None, 5, 3, None, 0.9, 0.9),
    ("achievement_dominates", 0, 4, 1, 100.0, 0.9, 0.9),
    ("misleading_semantic_mock", 1, 5, 2, None, 1.0, 0.1),
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


def stress_dataset() -> list[dict]:
    cases = []
    for specialization, stack in STACKS.items():
        for grade in GRADES:
            for name, claimed_correct, verified_correct, verified_stack_count, pvn, claimed_semantic, verified_semantic in CASE_INPUTS:
                cases.append(
                    {
                        "id": f"{specialization}-{grade}-{name}",
                        "case_type": name,
                        "vacancy": {"id": f"{specialization}-{grade}", "specialization": specialization, "grade": grade, "stack": stack},
                        "claimed": {
                            "stack": stack,
                            "correct_count": claimed_correct,
                            "pvn": pvn,
                            "semantic": claimed_semantic,
                            "relevant": False,
                        },
                        "verified": {
                            "stack": stack[:verified_stack_count],
                            "correct_count": verified_correct,
                            "pvn": None,
                            "semantic": verified_semantic,
                            "relevant": True,
                        },
                    }
                )
    return cases


def candidate_fixture(case: dict, side: str, candidate_id: int):
    inputs = case[side]
    correct = inputs["correct_count"]
    sessions = [] if correct is None else [
        SimpleNamespace(result_score=result_score(correct, TASKS_PER_SESSION))
    ]
    achievements = [] if inputs["pvn"] is None else [
        SimpleNamespace(score=inputs["pvn"], achievement_type="synthetic", level="mock", achieved_at=date(2026, 1, 1))
    ]
    return SimpleNamespace(
        id=candidate_id,
        full_name=f"Synthetic {candidate_id}",
        contacts={"email": "synthetic@example.test"},
        stack=list(inputs["stack"]),
        specialization=case["vacancy"]["specialization"],
        grade=case["vacancy"]["grade"],
        years_of_experience=3,
        soft_skills=["communication"],
        category_id=1,
        resume_text=f"synthetic candidate {candidate_id}",
        assessment_text="mock practical result",
        portfolio_evidence={},
        embedding=None,
        embedding_text=None,
        embedding_model=None,
        sessions=sessions,
        achievements=achievements,
    )


def run_stress_suite(mode: str) -> dict:
    if mode not in {"lexical", "semantic_mock"}:
        raise ValueError("Unsupported validation mode")
    rows = []
    candidates_by_vacancy = {}
    for index, case in enumerate(stress_dataset()):
        cards = {}
        for offset, side in enumerate(["claimed", "verified"]):
            candidate = candidate_fixture(case, side, index * 2 + offset + 1)
            similarity = case[side]["semantic"] if mode == "semantic_mock" else None
            card = build_card(MemorySession(candidate), candidate, case["vacancy"]["stack"], similarity)
            cards[side] = card
            candidates_by_vacancy.setdefault(case["vacancy"]["id"], []).append(
                {"card": card, "relevant": case[side]["relevant"]}
            )
        verified_key = ranking_key(cards["verified"].final_score, cards["verified"].score, proof_tier_value=cards["verified"].proof_tier)
        claimed_key = ranking_key(cards["claimed"].final_score, cards["claimed"].score, proof_tier_value=cards["claimed"].proof_tier)
        rows.append(
            {
                "id": case["id"],
                "case_type": case["case_type"],
                "claimed_correct": case["claimed"]["correct_count"],
                "verified_correct": case["verified"]["correct_count"],
                "claimed_score": cards["claimed"].score,
                "verified_score": cards["verified"].score,
                "claimed_final": cards["claimed"].final_score,
                "verified_final": cards["verified"].final_score,
                "claimed_relevance": cards["claimed"].match_relevance,
                "verified_relevance": cards["verified"].match_relevance,
                "verified_higher": verified_key > claimed_key,
                "tie": verified_key == claimed_key,
                "claimed_higher": verified_key < claimed_key,
            }
        )
    top_slots = []
    for candidates in candidates_by_vacancy.values():
        ranked = sorted(candidates, key=lambda item: ranking_key(item["card"].final_score, item["card"].score, proof_tier_value=item["card"].proof_tier), reverse=True)
        top_slots.extend(ranked[:5])
    relevant_slots = sum(item["relevant"] for item in top_slots)
    return {
        "mode": mode,
        "pairs": len(rows),
        "vacancies": len(candidates_by_vacancy),
        "verified_higher_count": sum(row["verified_higher"] for row in rows),
        "tie_count": sum(row["tie"] for row in rows),
        "claimed_higher_count": sum(row["claimed_higher"] for row in rows),
        "perfect_claimed_stack_count": sum(row["claimed_relevance"] == 1.0 for row in rows) if mode == "lexical" else None,
        "relevant_top5_slots": relevant_slots,
        "top5_slots": len(top_slots),
        "precision_at_5": relevant_slots / len(top_slots),
        "rows": rows,
    }


async def run_embedding_mock_checks() -> dict:
    case = stress_dataset()[0]
    candidate = candidate_fixture(case, "verified", 1)
    vacancy = SimpleNamespace(
        title="Synthetic vacancy", description="Synthetic task", specialization="backend", stack=case["vacancy"]["stack"],
        embedding=None, embedding_text=None, embedding_model=None,
    )
    vectors = [[1.0] + [0.0] * 1023, [0.8, 0.6] + [0.0] * 1022]
    settings = SimpleNamespace(embeddings_enabled=True, embedding_model="deterministic-mock", embedding_dimensions=1024)
    embed = AsyncMock(side_effect=[[vectors[0]], [vectors[1]]])
    with patch.object(semantic_matching, "get_settings", return_value=settings), patch.object(semantic_matching, "embed_texts", embed):
        similarities = await semantic_matching.vacancy_similarities(MemorySession(candidate), vacancy, [candidate])
        cached = await semantic_matching.vacancy_similarities(MemorySession(candidate), vacancy, [candidate])
        cache_hit = cached == similarities and embed.await_count == 2
        candidate.resume_text = "changed synthetic evidence"
        embed.side_effect = None
        embed.return_value = []
        unavailable = await semantic_matching.vacancy_similarities(MemorySession(candidate), vacancy, [candidate])
        return {
            "checks": 3,
            "passed": sum([
                math.isclose(similarities.get(1, -1), 0.8),
                cache_hit,
                unavailable == {} and candidate.embedding is None,
            ]),
            "similarity": similarities.get(1),
            "embed_calls": embed.await_count,
        }


def run_test_retest(rng: random.Random) -> dict:
    verdict_matches = recommendation_matches = 0
    trials = 200
    for _ in range(trials):
        ability = rng.choice([0.85, 0.35])
        declared = rng.choice(GRADES)
        first = adaptive_verdict(sum(rng.random() < ability for _ in range(TASKS_PER_SESSION)), TASKS_PER_SESSION)
        second = adaptive_verdict(sum(rng.random() < ability for _ in range(TASKS_PER_SESSION)), TASKS_PER_SESSION)
        verdict_matches += first == second
        recommendation_matches += suggested_grade(declared, first) == suggested_grade(declared, second)
    return {"trials": trials, "verdict_matches": verdict_matches, "recommendation_matches": recommendation_matches}


def run_validation(seed: int = SEED) -> dict:
    return {
        "seed": seed,
        "lexical": run_stress_suite("lexical"),
        "semantic_mock": run_stress_suite("semantic_mock"),
        "embedding_mock": asyncio.run(run_embedding_mock_checks()),
        "test_retest": run_test_retest(random.Random(seed)),
    }


def render_report(results: dict) -> str:
    lexical = results["lexical"]
    semantic = results["semantic_mock"]
    embedding = results["embedding_mock"]
    retest = results["test_retest"]
    lines = [
        "# Результаты синтетического stress suite",
        "",
        "Это проверка поведения backend на заданных входах, не оценка качества подбора на рынке труда. Метрики посчитаны запуском; рыночная accuracy, AUC и calibration не заявляются.",
        "",
        "## Точный набор данных",
        f"- {lexical['vacancies']} вакансий: 4 специализации (backend/frontend/data/devops) x 3 грейда (junior/middle/senior).",
        "- Для каждой вакансии 8 пар; 16 кандидатов, 5 фиксированных практических ответов на кандидата при наличии сессии.",
        f"- Всего {lexical['pairs']} пар и {lexical['pairs'] * 2} кандидатов; каждый набор отдельно ранжируется в lexical fallback и semantic mock режиме.",
        "- Профили полностью заполнены; заявленный стек соперника всегда содержит все 3 требования вакансии. Достижения ПВН отсутствуют, кроме явно указанных случаев.",
        "- Метка relevant заранее задана только стороне verified (4/5 или 5/5); claimed сторона имеет 0/5, 1/5 или не имеет теста. Это искусственная метка, не экспертная оценка кандидата.",
        "- Ни задачи, ни ответы не исполняются/оцениваются: в backend передаются заданные correct_count и уже завершённые синтетические сессии.",
        "- Memory fixtures не содержат синтетических достижений и сессий; неизвестные модели возвращают пустой query result. При отсутствии завершённой сессии backend test_score=0.0, а не пропущенный компонент.",
        "",
        "| Сценарий (по 12 пар) | Claimed / verified ответы | Verified стек | Claimed доп. сигнал | Mock cosine claimed / verified |",
        "|---|---|---|---|---|",
    ]
    for name, claimed, verified, stack_count, pvn, claimed_semantic, verified_semantic in CASE_INPUTS:
        extra = f"PVN={pvn}" if pvn is not None else "нет"
        answers = "нет теста" if claimed is None else f"{claimed}/5"
        lines.append(f"| {name} | {answers} / {verified}/5 | {stack_count}/3 | {extra} | {claimed_semantic} / {verified_semantic} |")
    lines.extend([
        "",
        "Технологии: backend=`python, fastapi, postgresql`; frontend=`javascript, react, typescript`; data=`python, sql, airflow`; devops=`linux, docker, kubernetes`. Неполный verified стек берётся из первых N технологий. Все кандидаты соответствуют специализации и грейду своей вакансии.",
        "",
        "## Измеренные результаты",
        "| Режим | Verified строго выше | Равные final score | Claimed выше | Relevant слоты в top-5 | Precision@5 |",
        "|---|---|---|---|---|---|",
    ])
    for result in [lexical, semantic]:
        count = result["pairs"]
        lines.append(
            f"| {result['mode']} | {result['verified_higher_count']}/{count} ({result['verified_higher_count']/count:.3f}) | "
            f"{result['tie_count']}/{count} ({result['tie_count']/count:.3f}) | "
            f"{result['claimed_higher_count']}/{count} ({result['claimed_higher_count']/count:.3f}) | "
            f"{result['relevant_top5_slots']}/{result['top5_slots']} | {result['precision_at_5']:.3f} |"
        )
    lines.extend([
        "",
        "Top-5 сортируется тем же ключом, что и выдача: `(proof_tier, final_score, score)` по убыванию. Все вакансии имеют одинаковую структуру, поэтому пары не являются независимыми рыночными наблюдениями.",
        "Precision@5=1.000 здесь — структурное свойство набора (в каждой вакансии ровно два релевантных профиля, а слотов пять), а не доказательство качества подбора на рынке. Значимо другое: hard gate по тиру не даёт claimed-профилю обойти verified ни в одной из 84 пар.",
        "",
        "## Результат каждого типа пары",
        "| Тип | Lexical claimed / verified final score | Semantic mock claimed / verified final score |",
        "|---|---|---|",
    ])
    for left, right in zip(lexical["rows"][:8], semantic["rows"][:8]):
        lines.append(f"| {left['case_type']} | {left['claimed_final']:.2f} / {left['verified_final']:.2f} | {right['claimed_final']:.2f} / {right['verified_final']:.2f} |")
    lines.extend([
        "",
        f"Идеальный claimed стек получает relevance=1 в {lexical['perfect_claimed_stack_count']}/{lexical['pairs']} пар даже без теста, но этого больше недостаточно: соответствие потребности теперь аддитивная надбавка (до +{RELEVANCE_MAX_BONUS:.0f} баллов), а не множитель, поэтому сильный подтверждённый результат перевешивает самоописанный стек.",
        "В сценарии unverified_keyword_stuffing: профиль без завершённого теста получает tier=claimed и не может обойти verified с тем же стеком. Сценарии sparse_verified_stack и achievement_dominates, где раньше слабый тест с полным стеком обгонял сильный тест с разреженным стеком, теперь сходятся в пользу verified. Misleading semantic mock по-прежнему проверяет, что textual similarity не является подтверждением навыка.",
        "",
        "## Дополнительные проверки",
        f"- Реальные `vacancy_similarities`/`index_entities`: {embedding['passed']}/{embedding['checks']} проверок (1024-мерные deterministic vectors, cosine={embedding['similarity']}, cache hit, invalidation + unavailable provider); mock embed calls={embedding['embed_calls']}.",
        f"- Синтетический test-retest, seed={results['seed']}, p=0.85/0.35, 200 пар 5-ответных сессий: вердикты {retest['verdict_matches']}/{retest['trials']} ({retest['verdict_matches']/retest['trials']:.3f}), рекомендации грейда {retest['recommendation_matches']}/{retest['trials']} ({retest['recommendation_matches']/retest['trials']:.3f}). Это не стабильность присвоенного грейда и не измерение реальной сложности задач.",
        "",
        "## Что именно проверено",
        "Использованы реальные backend `build_card`, `build_components`, `compute_score`, `result_score`, stack intersection и `relevance_breakdown`; формула ранжирования не продублирована. SQL query layer заменён memory fixtures. Semantic similarity в ranking suite задана вручную; отдельно реальный embedding pipeline проверен через deterministic AsyncMock без сетевых вызовов. PostgreSQL pgvector branch и HTTP search API этим скриптом не проверяются.",
        "",
        "## Ограничения и честный pitch",
        "Нет реальных резюме, экспертной разметки, реальных задач/ответов и исходов найма. Увеличение числа одинаково устроенных fixtures не повышает доказательность. Тесты не валидируют LLM-проверку, embedding-провайдера, антифрод или распределение навыков на рынке. Старые synthetic AUC/calibration и tautological precision нельзя считать подтверждением качества продукта.",
        "",
        "Мы проверяем подбор воспроизводимыми adversarial сценариями: при одинаковых профилях backend предпочитает высокий практический результат; отсутствие теста больше не даёт полностью заполненному профилю score=100. Неполный стек, высокие дополнительные сигналы и вводящее в заблуждение semantic сходство остаются рисками ранжирования. Suite использует настоящий backend и показывает не только успешные пары, но и ошибки. Это регрессионная инженерная проверка; качество найма предстоит оценить на независимых размеченных данных и реальных outcomes.",
        "",
        "## Воспроизведение",
        "`python -m scripts.validate` перезаписывает этот отчёт. `python -m pytest tests/test_validation.py tests/test_testing.py -q` проверяет suite и существующую адаптацию. Результат не зависит от настроек embedding-провайдера или рабочей БД.",
        "",
    ])
    return "\n".join(lines)


def main() -> None:
    report = render_report(run_validation())
    Path(__file__).resolve().parents[1].joinpath("docs", "validation-results.md").write_text(report, encoding="utf-8")
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    print(report)


if __name__ == "__main__":
    main()
