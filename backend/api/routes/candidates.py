from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from backend.api.deps import get_db, require_employer
from backend.core.config import get_settings
from backend.core.demo_filter import is_demo_visible
from backend.core.scoring import (
    PROOF_TIER_CLAIMED,
    ScoreComponents,
    compute_score,
    final_score as compute_final_score,
    has_pvn_history,
    is_verified,
    meets_relevance_floor,
    profile_completeness,
    proof_tier,
    rank_candidates,
    RankableCandidate,
)
from backend.models import (
    CandidateProfile,
    PvnAchievement,
    TestSession,
    User,
    Vacancy,
    EmployerProfile,
)
from backend.schemas.matching import CandidateCardResponse, CandidatePublicProfileResponse
from backend.services.candidate_score import build_stack_proof, build_stack_proof_bulk
from backend.services.reranking import rerank_enabled
from backend.services.semantic_matching import relevance_breakdown, stack_intersection, vacancy_similarities

router = APIRouter()


def visible_candidates(db: Session) -> list[CandidateProfile]:
    rows = (
        db.query(CandidateProfile, User)
        .join(User, CandidateProfile.user_id == User.id)
        .filter(CandidateProfile.is_visible == True)
        .all()
    )
    return [profile for profile, user in rows if is_demo_visible(user.email)]


def build_components(candidate: CandidateProfile, achievements, latest_session) -> ScoreComponents:
    pvn_score = None
    if achievements:
        pvn_score = min(100.0, sum(a.score for a in achievements))
    test_score = latest_session.result_score if latest_session else None
    return ScoreComponents(
        test_score=test_score,
        pvn_achievements=pvn_score,
        profile_completeness=profile_completeness(candidate),
    )


def match_relevance(candidate_stack: list, required_stack: list) -> float:
    return stack_intersection(candidate_stack, required_stack)


def card_proof_tier(components: ScoreComponents) -> str:
    return proof_tier(components)


def sort_cards(cards: list) -> list:
    ranked = rank_candidates(
        [
            RankableCandidate(
                final_score=card.final_score,
                score=card.score,
                proof_tier=getattr(card, "proof_tier", PROOF_TIER_CLAIMED),
            )
            for card in cards
        ]
    )
    by_key: dict[tuple[float, float, str], list] = {}
    for card in cards:
        key = (card.final_score, card.score, getattr(card, "proof_tier", PROOF_TIER_CLAIMED))
        by_key.setdefault(key, []).append(card)
    ordered = []
    for candidate in ranked:
        key = (candidate.final_score, candidate.score, candidate.proof_tier)
        ordered.extend(by_key.pop(key, []))
    return ordered


def verified_pvn_ids(db: Session, candidates: list[CandidateProfile]) -> dict[int, str]:
    user_ids = {candidate.user_id for candidate in candidates}
    if not user_ids:
        return {}
    rows = db.query(User.id, User.pvn_id).filter(User.id.in_(user_ids), User.pvn_id.isnot(None)).all()
    return {user_id: pvn_id for user_id, pvn_id in rows if pvn_id}


def card_stack_proof(
    db: Session, candidate: CandidateProfile, precomputed: list[dict] | None
) -> list[dict]:
    if precomputed is not None:
        return precomputed
    try:
        return build_stack_proof(db, candidate)
    except (AttributeError, TypeError):
        return []


def build_card(
    db: Session,
    candidate: CandidateProfile,
    required_stack: list,
    semantic_similarity: float | None = None,
    pvn_id: str | None = None,
    stack_proof: list[dict] | None = None,
) -> CandidateCardResponse:
    achievements = (
        db.query(PvnAchievement)
        .filter(PvnAchievement.candidate_profile_id == candidate.id)
        .all()
    )
    latest_session = (
        db.query(TestSession)
        .filter(
            TestSession.candidate_profile_id == candidate.id,
            TestSession.status == "completed",
        )
        .order_by(TestSession.completed_at.desc())
        .first()
    )
    components = build_components(candidate, achievements, latest_session)
    score, breakdown = compute_score(components)
    tier = card_proof_tier(components)
    match = relevance_breakdown(candidate.stack, required_stack, semantic_similarity)
    relevance = match["relevance"]
    return CandidateCardResponse(
        candidate_profile_id=candidate.id,
        grade=candidate.grade,
        specialization=candidate.specialization,
        city=getattr(candidate, "city", "") or "",
        work_format=getattr(candidate, "work_format", "") or "",
        stack=candidate.stack,
        score=score,
        score_breakdown=breakdown,
        has_pvn_history=has_pvn_history(components),
        is_pvn_verified=pvn_id is not None,
        pvn_achievements=[
            {"type": a.achievement_type, "level": a.level, "date": a.achieved_at.isoformat(), "score": a.score}
            for a in achievements
        ],
        match_relevance=round(relevance, 4),
        final_score=round(compute_final_score(score, relevance), 2),
        match_breakdown=match,
        proof_tier=tier,
        is_verified=is_verified(components),
        stack_proof=card_stack_proof(db, candidate, stack_proof),
    )


def build_public_profile(
    db: Session,
    candidate: CandidateProfile,
    vacancy: Vacancy | None,
    semantic_similarity: float | None = None,
) -> CandidatePublicProfileResponse:
    from backend.services.candidate_score import build_stack_proof

    achievements = (
        db.query(PvnAchievement)
        .filter(PvnAchievement.candidate_profile_id == candidate.id)
        .all()
    )
    latest_session = (
        db.query(TestSession)
        .filter(
            TestSession.candidate_profile_id == candidate.id,
            TestSession.status == "completed",
        )
        .order_by(TestSession.completed_at.desc())
        .first()
    )
    components = build_components(candidate, achievements, latest_session)
    score, breakdown = compute_score(components)
    relevance: float | None = None
    if vacancy is not None:
        relevance = round(relevance_breakdown(candidate.stack, vacancy.stack, semantic_similarity)["relevance"], 4)
    return CandidatePublicProfileResponse(
        candidate_profile_id=candidate.id,
        grade=candidate.grade,
        specialization=candidate.specialization or "",
        stack_proof=build_stack_proof(db, candidate),
        years_of_experience=candidate.years_of_experience or 0.0,
        soft_skills=list(candidate.soft_skills or []),
        city=candidate.city or "",
        work_format=candidate.work_format or "",
        proof_tier=card_proof_tier(components),
        is_verified=is_verified(components),
        score=score,
        score_breakdown=breakdown,
        match_relevance=relevance,
        pvn_achievements=[
            {"type": a.achievement_type, "level": a.level}
            for a in achievements
        ],
    )


def find_visible_candidate(db: Session, candidate_profile_id: int) -> CandidateProfile:
    row = (
        db.query(CandidateProfile, User)
        .join(User, CandidateProfile.user_id == User.id)
        .filter(CandidateProfile.id == candidate_profile_id)
        .first()
    )
    if row is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Кандидат не найден")
    profile, user = row
    if not profile.is_visible or not is_demo_visible(user.email):
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Кандидат не найден")
    return profile


@router.get("/candidates/{candidate_profile_id}", response_model=CandidatePublicProfileResponse)
async def get_candidate_public_profile(
    candidate_profile_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(require_employer),
    vacancy_id: int | None = Query(default=None, ge=1),
):
    candidate = find_visible_candidate(db, candidate_profile_id)
    vacancy = resolve_vacancy(db, user, vacancy_id)
    similarity = None
    if vacancy is not None:
        similarities = await vacancy_similarities(db, vacancy, [candidate])
        similarity = similarities.get(candidate.id)
        db.commit()
    return build_public_profile(db, candidate, vacancy, similarity)


def domain_candidate_counts(db: Session) -> dict[int, int]:
    from backend.core.domain_matching import domain_matches_candidate
    from backend.models import Domain

    domains = db.query(Domain).all()
    counts: dict[int, int] = {}
    for domain in domains:
        counts[domain.id] = 0
    for candidate in visible_candidates(db):
        for domain in domains:
            if domain_matches_candidate(domain, candidate.specialization, candidate.stack):
                counts[domain.id] = counts.get(domain.id, 0) + 1
    return counts


async def apply_rerank(query: str, candidates: list) -> list:
    from backend.services.reranking import rerank
    from backend.services.semantic_matching import normalize_rerank_scores, rerank_documents

    if not rerank_enabled():
        return candidates
    top_n = get_settings().rerank_top_n
    head = list(candidates[:top_n])
    tail = list(candidates[top_n:])
    documents = [" \n".join(part for part in rerank_documents(candidate) if part) for candidate in head]
    ranked = await rerank(query, documents, top_n=len(head))
    if not ranked:
        return None
    order = {index: score for index, score in ranked}
    indexed = list(enumerate(head))
    indexed.sort(key=lambda item: order.get(item[0], 0.0), reverse=True)
    return [candidate for _, candidate in indexed] + tail


def apply_card_filters(
    cards: list,
    has_pvn: bool | None,
    min_score: float | None,
    verified_only: bool | None = None,
    require_relevance: bool = False,
    city: str | None = None,
    work_format: str | None = None,
) -> list:
    filtered = cards
    if has_pvn is not None:
        filtered = [c for c in filtered if c.has_pvn_history == has_pvn]
    if verified_only is not None:
        filtered = [c for c in filtered if c.is_pvn_verified == verified_only]
    if min_score is not None:
        filtered = [c for c in filtered if c.score >= min_score]
    if require_relevance:
        filtered = [c for c in filtered if meets_relevance_floor(c.match_relevance)]
    city_token = (city or "").strip().lower()
    if city_token:
        filtered = [c for c in filtered if (c.city or "").strip().lower() == city_token]
    format_token = (work_format or "").strip().lower()
    if format_token:
        filtered = [c for c in filtered if (c.work_format or "").strip().lower() == format_token]
    return filtered


def stack_matches(candidate_stack: list, required_stack: list) -> bool:
    if not required_stack:
        return True
    candidate = [s.strip().lower() for s in (candidate_stack or []) if s and s.strip()]
    for required in required_stack:
        for token in str(required).replace(",", " ").split():
            token = token.strip().lower()
            if token == '':
                continue
            if any(token in skill or skill in token for skill in candidate):
                return True
    return False


@router.get("/categories/{category_id}/cards", response_model=list[CandidateCardResponse])
def list_category_cards(
    category_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(require_employer),
    stack: list[str] | None = Query(default=None),
    has_pvn: bool | None = Query(default=None),
    verified_only: bool | None = Query(default=None),
    min_score: float | None = Query(default=None, ge=0, le=100),
    city: str | None = Query(default=None, max_length=128),
    work_format: str | None = Query(default=None, max_length=16),
    skip: int = Query(default=0, ge=0),
    limit: int = Query(default=50, ge=1, le=200),
):
    from backend.models import Category

    category = db.get(Category, category_id)
    if category is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Категория не найдена")
    candidates = [c for c in visible_candidates(db) if c.category_id == category_id]
    if stack:
        candidates = [c for c in candidates if stack_matches(c.stack, stack)]
    verified = verified_pvn_ids(db, candidates)
    proofs = build_stack_proof_bulk(db, candidates)
    cards = apply_card_filters(
        [
            build_card(
                db,
                c,
                stack or [],
                pvn_id=verified.get(c.user_id),
                stack_proof=proofs.get(c.id),
            )
            for c in candidates
        ],
        has_pvn,
        min_score,
        verified_only,
        city=city,
        work_format=work_format,
    )
    cards = sort_cards(cards)
    return cards[skip : skip + limit]


def resolve_vacancy(db: Session, user: User, vacancy_id: int | None) -> Vacancy | None:
    if vacancy_id is None:
        return None
    vacancy = db.get(Vacancy, vacancy_id)
    employer = db.query(EmployerProfile).filter(EmployerProfile.user_id == user.id).first()
    if vacancy is None or employer is None or vacancy.employer_profile_id != employer.id:
        raise HTTPException(status_code=404, detail="Вакансия не найдена")
    return vacancy


def filter_by_specialization(db: Session, candidates: list, specialization: str) -> list:
    from backend.core.domain_matching import domain_matches_candidate, nearest_domain
    from backend.models import Domain

    token = specialization.strip()
    matched = nearest_domain(token, db.query(Domain).all(), threshold=0.9)
    if matched is not None:
        return [c for c in candidates if domain_matches_candidate(matched, c.specialization, c.stack)]
    lowered = token.lower()
    return [c for c in candidates if lowered in (c.specialization or "").lower()]


def filter_by_grade(candidates: list, grade: str) -> list:
    token = grade.strip().lower()
    return [c for c in candidates if (c.grade or "").lower() == token]


def filter_by_query(query_text: str) -> "callable":
    async def run(db: Session, candidates: list) -> list:
        from backend.core.domain_matching import domain_matches_candidate, terms_match_query
        from backend.services.domain_search import search_domains

        ranked = await search_domains(db, query_text, limit=5)
        best = ranked[0][1] if ranked else 0.0
        cutoff = max(best - 0.2, 0.45)
        strong = [domain for domain, score in ranked if score >= cutoff]
        if strong:
            return [c for c in candidates if any(domain_matches_candidate(domain, c.specialization, c.stack) for domain in strong)]
        terms = [query_text]
        for domain in strong:
            terms.extend(alias for alias in (domain.aliases or []) if len(alias.strip()) >= 4)
            terms.append(domain.title)
        return [
            c
            for c in candidates
            if terms_match_query(c.specialization or "", terms, threshold=0.62)
            or any(terms_match_query(skill, terms, threshold=0.7) for skill in (c.stack or []))
        ]

    return run


@router.get("/search", response_model=list[CandidateCardResponse])
async def search_candidates(
    db: Session = Depends(get_db),
    user: User = Depends(require_employer),
    q: str | None = Query(default=None, max_length=128),
    vacancy_id: int | None = Query(default=None, ge=1),
    specialization: str | None = Query(default=None),
    grade: str | None = Query(default=None),
    stack: list[str] | None = Query(default=None),
    has_pvn: bool | None = Query(default=None),
    verified_only: bool | None = Query(default=None),
    min_score: float | None = Query(default=None, ge=0, le=100),
    city: str | None = Query(default=None, max_length=128),
    work_format: str | None = Query(default=None, max_length=16),
    skip: int = Query(default=0, ge=0),
    limit: int = Query(default=50, ge=1, le=200),
):
    candidates = visible_candidates(db)
    vacancy = resolve_vacancy(db, user, vacancy_id)
    if specialization is not None:
        candidates = filter_by_specialization(db, candidates, specialization)
    if grade is not None:
        candidates = filter_by_grade(candidates, grade)
    if q is not None and q.strip():
        candidates = await filter_by_query(q.strip())(db, candidates)
    if stack:
        candidates = [c for c in candidates if stack_matches(c.stack, stack)]
    similarities = {}
    if vacancy is not None:
        similarities = await vacancy_similarities(db, vacancy, candidates)
        db.commit()
    reranked = False
    if q is not None and q.strip() and candidates:
        reranked_order = await apply_rerank(q.strip(), candidates)
        reranked = reranked_order is not None
        if reranked_order is not None:
            candidates = reranked_order
    verified = verified_pvn_ids(db, candidates)
    proofs = build_stack_proof_bulk(db, candidates)
    cards = apply_card_filters(
        [
            build_card(
                db,
                c,
                vacancy.stack if vacancy is not None else stack or [],
                similarities.get(c.id),
                verified.get(c.user_id),
                stack_proof=proofs.get(c.id),
            )
            for c in candidates
        ],
        has_pvn,
        min_score,
        verified_only,
        city=city,
        work_format=work_format,
    )
    if not reranked:
        cards = sort_cards(cards)
    return cards[skip : skip + limit]
