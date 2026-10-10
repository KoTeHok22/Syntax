from backend.db import Base, SessionLocal, engine, ensure_vector_extension
from backend.models import Concept, TaskContext
from scripts.concept_bank import CONCEPTS, CONTEXT_LABELS


def seed_concepts() -> int:
    db = SessionLocal()
    inserted = 0
    try:
        for entry in CONCEPTS:
            existing = (
                db.query(Concept)
                .filter(Concept.name == entry["name"], Concept.grade == entry["grade"])
                .first()
            )
            if existing is not None:
                continue
            db.add(
                Concept(
                    name=entry["name"],
                    domain=entry["domain"],
                    grade=entry["grade"],
                    difficulty_params=entry["params"],
                    task_format="multiple_choice",
                    question_template=entry["question"],
                    correct_answer=entry["correct"],
                    distractors=entry["distractors"],
                )
            )
            inserted += 1
        db.commit()
    finally:
        db.close()
    return inserted


def seed_contexts() -> int:
    db = SessionLocal()
    inserted = 0
    try:
        for label in CONTEXT_LABELS:
            if db.query(TaskContext).filter(TaskContext.label == label).first() is None:
                db.add(TaskContext(label=label))
                inserted += 1
        db.commit()
    finally:
        db.close()
    return inserted


if __name__ == "__main__":
    ensure_vector_extension(engine)
    Base.metadata.create_all(bind=engine)
    concepts_count = seed_concepts()
    contexts_count = seed_contexts()
    print(f"Добавлено концептов: {concepts_count} из {len(CONCEPTS)}")
    print(f"Добавлено контекстов генерации: {contexts_count} из {len(CONTEXT_LABELS)}")
