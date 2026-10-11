import json
import math
import random
import statistics
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from scripts.concept_bank import CONCEPTS

SEED = 20260114
TASKS_PER_SESSION = 20
CANDIDATE_COUNT = 5000
GRID_MIN = -4.0
GRID_MAX = 4.0
GRID_STEP = 0.01

THETA_MU = 0.0
THETA_SIGMA = 1.0

DISCRIMINATION = {
    "junior": 1.0,
    "middle": 1.1,
    "senior": 1.2,
}
DIFFICULTY_CENTER = {
    "junior": -1.0,
    "middle": 0.0,
    "senior": 1.0,
}
DIFFICULTY_SPREAD = {
    "junior": 0.35,
    "middle": 0.45,
    "senior": 0.60,
}
TARGETING_OFFSET = 0.0

GRADE_ORDER = ["junior", "middle", "senior"]

RELIABILITY_BENCHMARKS = [
    (0.90, 3, 4),
    (0.80, 2, 3),
    (0.50, 1, 2),
]

SOURCES = [
    "https://www.winsteps.com/winman/standarderrors.htm",
    "https://www.winsteps.com/winman/reliability.htm",
    "https://www.rasch.org/rmt/rmt94n.htm",
    "https://www.rasch.org/rmt/rmt163f.htm",
]


def clamp(value, low, high):
    return max(low, min(high, value))


def item_difficulty(concept, rng):
    grade = concept["grade"]
    center = DIFFICULTY_CENTER[grade]
    spread = DIFFICULTY_SPREAD[grade]
    jitter = rng.uniform(-spread, spread)
    return center + jitter


def item_discrimination(concept):
    return DISCRIMINATION[concept["grade"]]


def build_item_bank(rng):
    items = []
    for concept in CONCEPTS:
        items.append(
            {
                "name": concept["name"],
                "domain": concept["domain"],
                "grade": concept["grade"],
                "b": item_difficulty(concept, rng),
                "a": item_discrimination(concept),
            }
        )
    return items


def probability_correct(theta, a, b):
    return 1.0 / (1.0 + math.exp(-a * (theta - b)))


def item_information(theta, a, b):
    p = probability_correct(theta, a, b)
    return (a * a) * p * (1.0 - p)


def test_information(theta, items):
    return sum(item_information(theta, item["a"], item["b"]) for item in items)


def standard_error(theta, items):
    info = test_information(theta, items)
    if info <= 0.0:
        return float("inf")
    return 1.0 / math.sqrt(info)


def population_sd(values):
    mean = statistics.fmean(values)
    variance = statistics.fmean((value - mean) ** 2 for value in values)
    return math.sqrt(variance)


def separation_from_reliability(reliability):
    if reliability <= 0.0:
        return 0.0
    if reliability >= 1.0:
        return float("inf")
    return math.sqrt(reliability / (1.0 - reliability))


def strata_from_separation(separation):
    return (4.0 * separation + 1.0) / 3.0


def spearman_brown(current_reliability, current_length, target_length):
    if current_length <= 0 or current_reliability <= 0.0:
        return 0.0
    numerator = target_length * current_reliability
    denominator = current_length * (1.0 - current_reliability) + target_length * current_reliability
    if denominator <= 0.0:
        return 0.0
    return numerator / denominator


def simulate_theta(items, rng):
    true_theta = []
    raw_scores = []
    for _ in range(CANDIDATE_COUNT):
        theta = rng.gauss(THETA_MU, THETA_SIGMA) + TARGETING_OFFSET
        score = 0
        for item in items:
            p = probability_correct(theta, item["a"], item["b"])
            if rng.random() < p:
                score += 1
        true_theta.append(theta)
        raw_scores.append(score)
    return true_theta, raw_scores


def build_score_theta_table(items, grid):
    table = {}
    for theta in grid:
        score = round(expected_score(theta, items))
        if score not in table:
            table[score] = theta
    return table


def theta_estimate_from_score(raw_score, items, grid):
    best_theta = GRID_MIN
    best_distance = abs(expected_score(GRID_MIN, items) - raw_score)
    theta = GRID_MIN + GRID_STEP
    while theta <= GRID_MAX:
        distance = abs(expected_score(theta, items) - raw_score)
        if distance < best_distance:
            best_distance = distance
            best_theta = theta
        theta += GRID_STEP
    return best_theta


def expected_score(theta, items):
    return sum(probability_correct(theta, item["a"], item["b"]) for item in items)


def reliability_from_estimates(true_theta, estimated_theta):
    observed_variance = population_sd(estimated_theta) ** 2
    error_variance = statistics.fmean(
        (estimate - truth) ** 2 for truth, estimate in zip(true_theta, estimated_theta)
    )
    if observed_variance <= 0.0:
        return 0.0
    reliability = (observed_variance - error_variance) / observed_variance
    return clamp(reliability, 0.0, 1.0)


def mean_se_theta(items, grid):
    values = [standard_error(theta, items) for theta in grid]
    return statistics.fmean(values)


def reliability_benchmark_levels(reliability):
    for threshold, low, high in RELIABILITY_BENCHMARKS:
        if reliability >= threshold:
            return low, high
    return 1, 2


def distinct_bands(reliability, candidate_count):
    separation = separation_from_reliability(reliability)
    strata = strata_from_separation(separation)
    distinguishable = int(clamp(math.floor(strata), 1, candidate_count))
    return separation, strata, distinguishable


def grade_pass_difficulty(grades_present):
    return statistics.fmean(DIFFICULTY_CENTER[grade] for grade in grades_present)


def simulate(rng):
    items = build_item_bank(rng)
    session_items = items[:TASKS_PER_SESSION]

    grid = [GRID_MIN + index * GRID_STEP for index in range(int(round((GRID_MAX - GRID_MIN) / GRID_STEP)) + 1)]

    theta_true, raw_scores = simulate_theta(session_items, rng)
    score_theta = build_score_theta_table(session_items, grid)
    theta_hat = [score_theta.get(score, theta_estimate_from_score(score, session_items, grid)) for score in raw_scores]

    reliability = reliability_from_estimates(theta_true, theta_hat)
    separation, strata, bands = distinct_bands(reliability, CANDIDATE_COUNT)
    benchmark_low, benchmark_high = reliability_benchmark_levels(reliability)

    mid_se = mean_se_theta(session_items, grid)
    grid_se = {round(theta, 2): standard_error(theta, session_items) for theta in (-2.0, -1.0, 0.0, 1.0, 2.0)}
    peak_info_theta = max(grid, key=lambda theta: test_information(theta, session_items))
    peak_se = standard_error(peak_info_theta, session_items)

    half_length = max(1, TASKS_PER_SESSION // 2)
    half_items = session_items[:half_length]
    half_reliability = spearman_brown(reliability, TASKS_PER_SESSION, half_length)
    double_length = TASKS_PER_SESSION * 2
    double_reliability = spearman_brown(reliability, TASKS_PER_SESSION, double_length)

    grade_pass = {grade: grade_pass_difficulty([grade]) for grade in GRADE_ORDER}
    max_grade_gap = max(
        abs(grade_pass["middle"] - grade_pass["junior"]),
        abs(grade_pass["senior"] - grade_pass["middle"]),
    )
    detectable_gap = separation * mid_se

    result = {
        "seed": SEED,
        "tasks_per_session": TASKS_PER_SESSION,
        "candidate_count": CANDIDATE_COUNT,
        "concept_count": len(items),
        "session_item_count": len(session_items),
        "mean_se_theta": round(mid_se, 4),
        "se_theta_by_level": {str(level): round(value, 4) for level, value in grid_se.items()},
        "peak_information_theta": round(peak_info_theta, 4),
        "peak_se_theta": round(peak_se, 4),
        "reliability": round(reliability, 4),
        "separation_index": round(separation, 4),
        "strata": round(strata, 4),
        "distinguishable_bands": bands,
        "benchmark_bands_low": benchmark_low,
        "benchmark_bands_high": benchmark_high,
        "spearman_brown_half_length_reliability": round(half_reliability, 4),
        "spearman_brown_double_length_reliability": round(double_reliability, 4),
        "grade_pass_difficulty": {grade: round(value, 4) for grade, value in grade_pass.items()},
        "max_grade_gap": round(max_grade_gap, 4),
        "detectable_grade_gap": round(detectable_gap, 4),
        "grades_separable": bool(detectable_gap >= max_grade_gap),
        "discrimination_by_grade": dict(DISCRIMINATION),
        "difficulty_center_by_grade": dict(DIFFICULTY_CENTER),
        "difficulty_spread_by_grade": dict(DIFFICULTY_SPREAD),
        "sources": SOURCES,
    }
    return result


def render_markdown(result):
    lines = [
        "# Психометрическая калибровка банка концептов",
        "",
        "Офлайн-калибровка item bank в терминах IRT/Rasch. Синтетическая симуляция, не оценка на реальных кандидатах.",
        "",
        "## Вход",
        f"- Концептов в банке: {result['concept_count']}; в сессию берётся {result['session_item_count']} (TASKS_PER_SESSION={result['tasks_per_session']}).",
        f"- Кандидатов в симуляции: {result['candidate_count']}, θ ~ N(0, 1), seed={result['seed']}.",
        "",
        "## Модель",
        "- Трудность b концепта: центр грейда (junior −1.0, middle 0.0, senior +1.0) плюс равномерный разброс (junior ±0.35, middle ±0.45, senior ±0.60).",
        "- Дискриминация a: junior 1.0, middle 1.1, senior 1.2 (2PL-стиль; Rasch a=1).",
        "- P(верно|θ) = 1 / (1 + exp(−a(θ−b))); информация I(θ) = a²·P·(1−P).",
        "- SE(θ) = 1 / sqrt(Σ I(θ)); надёжность = (наблюдаемая дисперсия − дисперсия ошибки) / наблюдаемая дисперсия.",
        "- Разделение = sqrt(Rel/(1−Rel)); strata = (4·Separation + 1)/3.",
        "",
        "## Вывод",
        f"- SE(θ) в центре (θ=0): **{result['se_theta_by_level']['0.0']}** логит; средний SE по сетке: {result['mean_se_theta']}.",
    ]
    for level, value in result["se_theta_by_level"].items():
        lines.append(f"  - θ={level}: SE={value}")
    lines.extend(
        [
            f"- Надёжность (person reliability): **{result['reliability']}**.",
            f"- Separation index: **{result['separation_index']}**; strata: **{result['strata']}**.",
            f"- Различимых band'ов (junior/middle/senior): **{result['distinguishable_bands']}** из 3.",
            f"- Бенчмарк Winsteps по надёжности {result['reliability']}: {result['benchmark_bands_low']}–{result['benchmark_bands_high']} уровня.",
            f"- Spearman-Brown: при {result['tasks_per_session'] // 2} задачах Rel={result['spearman_brown_half_length_reliability']}, при {result['tasks_per_session'] * 2} Rel={result['spearman_brown_double_length_reliability']}.",
            f"- Трудность проходного порога по грейдам: {json.dumps(result['grade_pass_difficulty'], ensure_ascii=False)}; максимальный разрыв между грейдами {result['max_grade_gap']} логит.",
            f"- Сессия различает грейды (SE·Separation ≥ разрыв): {'да' if result['grades_separable'] else 'нет'} (достижимо {result['detectable_grade_gap']} логит).",
            "",
            "## Ограничения",
            "- Синтетические ответы: b и a назначены из грейда, а не оценены на реальных кандидатах. Настоящая калибровка требует ответов ≥200 кандидатов на концепт.",
            "- Дискриминация a не измерена; при реальном a ниже 1 число различимых band'ов падает.",
            "- θ ~ N(0, 1) предполагает однородную популяцию; реальная выборка может быть смещена.",
            "- Числа обоснованы формулами IRT (см. источники), но не валидированы на людях.",
            "",
            "## Источники",
        ]
    )
    for source in result["sources"]:
        lines.append(f"- {source}")
    lines.append("")
    return "\n".join(lines)


def main():
    rng = random.Random(SEED)
    result = simulate(rng)
    markdown = render_markdown(result)

    output_dir = Path(__file__).resolve().parent.parent / "docs"
    output_dir.mkdir(parents=True, exist_ok=True)
    target = output_dir / "psychometrics-results.md"
    target.write_text(markdown, encoding="utf-8")

    print(json.dumps(result, ensure_ascii=False, indent=2))
    print(f"\nЗаписано: {target}")


if __name__ == "__main__":
    main()
