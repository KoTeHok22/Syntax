from backend.db import Base, SessionLocal, engine, ensure_vector_extension
from backend.models import Concept, Task, TaskContext
from backend.services.task_generation import fallback_task
from scripts.concept_bank import CONTEXT_LABELS

VARIANTS_PER_CONCEPT = 6


def generate_pool() -> int:
    db = SessionLocal()
    created = 0
    try:
        context_labels = [row.label for row in db.query(TaskContext).all()]
        if not context_labels:
            from backend.models import TaskContext as TC

            for label in CONTEXT_LABELS:
                db.add(TC(label=label))
            db.commit()
            context_labels = [row.label for row in db.query(TaskContext).all()]
        concepts = db.query(Concept).all()
        for concept in concepts:
            existing = (
                db.query(Task)
                .filter(Task.concept_id == concept.id, Task.candidate_profile_id.is_(None), Task.session_id.is_(None))
                .count()
            )
            for variant in range(max(0, VARIANTS_PER_CONCEPT - existing)):
                draft = fallback_task(concept, f"pool:{concept.name}:{concept.grade}:{variant}", context_labels)
                if draft is None:
                    continue
                db.add(
                    Task(
                        concept_id=concept.id,
                        grade=concept.grade,
                        statement=draft.statement,
                        task_format=draft.task_format,
                        options=draft.options,
                        reference_answer=draft.reference_answer,
                    )
                )
                created += 1
        db.commit()
    finally:
        db.close()
    return created


if __name__ == "__main__":
    ensure_vector_extension(engine)
    Base.metadata.create_all(bind=engine)
    count = generate_pool()
    print(f"Добавлено задач в fallback-пул: {count}")
    print(f"Целевое покрытие: {VARIANTS_PER_CONCEPT} вариантов на концепт")
