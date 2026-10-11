from dataclasses import dataclass, fields

WEIGHTS = {
    "test_score": 0.4,
    "pvn_achievements": 0.3,
    "profile_completeness": 0.1,
}

PROOF_TIER_VERIFIED = "verified"
PROOF_TIER_CLAIMED = "claimed"

PROOF_TIER_RANK = {
    PROOF_TIER_VERIFIED: 1,
    PROOF_TIER_CLAIMED: 0,
}

RELEVANCE_MAX_BONUS = 20.0
RELEVANCE_MIN = 0.2

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


def final_score(
    score: float,
    match_relevance: float,
    proof_tier_value: str | None = None,
) -> float:
    return score + match_relevance * RELEVANCE_MAX_BONUS


def meets_relevance_floor(match_relevance: float) -> bool:
    return match_relevance >= RELEVANCE_MIN


def has_pvn_history(components: ScoreComponents) -> bool:
    return components.pvn_achievements is not None


def proof_tier(components: ScoreComponents) -> str:
    if components.test_score is None:
        return PROOF_TIER_CLAIMED
    return PROOF_TIER_VERIFIED


def is_verified(components: ScoreComponents) -> bool:
    return proof_tier(components) == PROOF_TIER_VERIFIED


def ranking_key(
    final_score: float,
    score: float,
    components: ScoreComponents | None = None,
    proof_tier_value: str | None = None,
) -> tuple[int, float, float]:
    tier = proof_tier_value
    if tier is None and components is not None:
        tier = proof_tier(components)
    if tier is None:
        tier = PROOF_TIER_CLAIMED
    return (PROOF_TIER_RANK.get(tier, 0), final_score, score)


def ranks_above(
    candidate: "RankableCandidate",
    other: "RankableCandidate",
) -> bool:
    return ranking_key(
        candidate.final_score,
        candidate.score,
        proof_tier_value=candidate.proof_tier,
    ) > ranking_key(
        other.final_score,
        other.score,
        proof_tier_value=other.proof_tier,
    )


@dataclass(frozen=True)
class RankableCandidate:
    final_score: float
    score: float
    proof_tier: str = PROOF_TIER_CLAIMED


def rank_candidates(candidates: list["RankableCandidate"]) -> list["RankableCandidate"]:
    return sorted(
        candidates,
        key=lambda candidate: ranking_key(
            candidate.final_score,
            candidate.score,
            proof_tier_value=candidate.proof_tier,
        ),
        reverse=True,
    )


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
