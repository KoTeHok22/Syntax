import asyncio
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from backend.db import SessionLocal  # noqa: E402
from backend.models import Concept, EmployerProfile, RegularTask, User, Vacancy  # noqa: E402
from backend.services.task_generation import llm_task  # noqa: E402

DEMO_EMPLOYER_EMAIL = "demo-employer@example.com"
CONCEPTS_PER_DOMAIN = 2
MAX_ATTEMPTS = 3


async def generate_with_retries(concept: Concept):
    for _ in range(MAX_ATTEMPTS):
        draft = await llm_task(concept, concept.grade)
        if draft is not None:
            return draft
    return None


async def main() -> None:
    db = SessionLocal()
    try:
        user = db.query(User).filter(User.email == DEMO_EMPLOYER_EMAIL).first()
        employer = db.query(EmployerProfile).filter(EmployerProfile.user_id == user.id).first() if user else None
        if employer is None:
            raise SystemExit("Демо-работодатель не найден")

        concepts = db.query(Concept).order_by(Concept.domain, Concept.id).all()
        by_domain: dict[str, list[Concept]] = {}
        for concept in concepts:
            by_domain.setdefault(concept.domain, []).append(concept)
        chosen = [concept for group in by_domain.values() for concept in group[:CONCEPTS_PER_DOMAIN]]

        drafts = await asyncio.gather(*(generate_with_retries(concept) for concept in chosen))

        failed = [concept.name for concept, draft in zip(chosen, drafts) if draft is None]
        if failed:
            raise SystemExit(f"LLM не вернул задания для: {', '.join(failed)}")

        vacancies = (
            db.query(Vacancy)
            .filter(Vacancy.employer_profile_id == employer.id, Vacancy.status == "open")
            .order_by(Vacancy.id)
            .all()
        )
        if not vacancies:
            raise SystemExit("У демо-работодателя нет открытых вакансий")

        def vacancy_for(concept: Concept) -> Vacancy:
            matches = [vacancy for vacancy in vacancies if vacancy.specialization == concept.domain]
            return (matches or vacancies)[0]

        db.query(RegularTask).filter(RegularTask.employer_profile_id == employer.id).update({"is_active": False})
        for concept, draft in zip(chosen, drafts):
            db.add(
                RegularTask(
                    employer_profile_id=employer.id,
                    vacancy_id=vacancy_for(concept).id,
                    concept_id=concept.id,
                    statement=draft.statement,
                    task_format=draft.task_format,
                    options=draft.options,
                    reference_answer=draft.reference_answer,
                    is_active=True,
                )
            )
        db.commit()
        print(f"Создано заданий: {len(chosen)}")
    finally:
        db.close()


if __name__ == "__main__":
    asyncio.run(main())
