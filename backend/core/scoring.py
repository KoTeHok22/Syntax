from dataclasses import dataclass, fields

WEIGHTS = {
    "test_score": 0.4,
    "pvn_achievements": 0.3,
    "profile_completeness": 0.1,
}

COMPONENT_LABELS = {
    "test_score": "Результат тестирования",
    "pvn_achievements": "Достижения ПВН",
    "profile_completeness": "Полнота профиля",
}


@dataclass
class ScoreComponents:
    test_score: float | None = None
    pvn_achievements: float | None = None
    profile_completeness: float = 0.0


def compute_score(components: ScoreComponents) -> tuple[float, dict]:
    values = {
        field.name: getattr(components, field.name)
        for field in fields(components)
        if getattr(components, field.name) is not None
    }
    total_weight = sum(WEIGHTS[name] for name in values)
    breakdown = {}
    weighted_sum = 0.0
    for name, value in values.items():
        normalized_weight = WEIGHTS[name] / total_weight
        weighted_sum += value * normalized_weight
        breakdown[name] = {
            "label": COMPONENT_LABELS[name],
            "value": round(value, 2),
            "weight": round(normalized_weight, 4),
        }
    return round(weighted_sum, 2), breakdown


def has_pvn_history(components: ScoreComponents) -> bool:
    return components.pvn_achievements is not None


def profile_completeness(profile) -> float:
    checks = [
        bool(profile.full_name),
        bool(profile.contacts),
        bool(profile.stack),
        bool(profile.specialization),
        profile.years_of_experience > 0,
        bool(profile.soft_skills),
        profile.grade is not None,
        profile.category_id is not None,
    ]
    return 100.0 * sum(1 for c in checks if c) / len(checks)
