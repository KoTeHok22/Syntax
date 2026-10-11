import hashlib

from sqlalchemy.orm import Session

from backend.db import Base, SessionLocal, engine, ensure_vector_extension
from scripts import backfill_grade_confirmation, generate_synthetic, generate_task_pool, seed


def _stable_index(key: str, size: int) -> int:
    digest = hashlib.sha256(key.encode("utf-8")).digest()
    return int.from_bytes(digest[:8], "big") % size


def backfill_demo_profile_fields(db: Session) -> int:
    updated = 0
    for profile in backfill_grade_confirmation.demo_profiles(db):
        key = f"{profile.id}:{profile.user_id}"
        if not (profile.city or "").strip():
            profile.city = generate_synthetic.CITIES[_stable_index(f"city:{key}", len(generate_synthetic.CITIES))]
            updated += 1
        if not (profile.work_format or "").strip():
            profile.work_format = generate_synthetic.WORK_FORMATS[
                _stable_index(f"format:{key}", len(generate_synthetic.WORK_FORMATS))
            ]
            updated += 1
    db.commit()
    return updated


def reconcile_demo_data(db: Session) -> tuple[int, int]:
    fields = backfill_demo_profile_fields(db)
    grades = backfill_grade_confirmation.backfill(db)
    return fields, grades


def main() -> None:
    ensure_vector_extension(engine)
    Base.metadata.create_all(bind=engine)
    seed.seed_concepts()
    seed.seed_contexts()
    generate_task_pool.generate_pool()
    generate_synthetic.main()
    db = SessionLocal()
    try:
        fields, grades = reconcile_demo_data(db)
    finally:
        db.close()
    print(f"Дозаполнено полей city/work_format: {fields}")
    print(f"Подтверждено грейдов: {grades}")


if __name__ == "__main__":
    main()
