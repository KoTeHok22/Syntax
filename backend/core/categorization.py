def category_key(specialization: str, grade: str) -> tuple[str, str]:
    return (specialization.strip().lower(), grade.strip().lower())


def resolve_category(db, specialization: str, grade: str):
    from backend.models import Category

    spec, gr = category_key(specialization, grade)
    return (
        db.query(Category)
        .filter(Category.specialization == spec, Category.grade == gr)
        .first()
    )


def assign_category(db, candidate_profile, specialization: str, grade: str):
    category = resolve_category(db, specialization, grade)
    if category is None:
        from backend.models import Category

        spec, gr = category_key(specialization, grade)
        category = Category(specialization=spec, grade=gr)
        db.add(category)
        db.flush()
    candidate_profile.category_id = category.id
    return category
