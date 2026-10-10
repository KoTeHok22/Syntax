from fastapi import APIRouter, Depends, Query
from sqlalchemy import or_
from sqlalchemy.orm import Session

from backend.api.deps import get_db, require_employer
from backend.api.routes.candidates import visible_candidates
from backend.models import Category, User
from backend.schemas.matching import CategoryPage, CategoryResponse

router = APIRouter()


@router.get("/categories", response_model=CategoryPage)
def list_categories(
    specialization: str | None = Query(default=None),
    grade: str | None = Query(default=None),
    q: str | None = Query(default=None, max_length=64),
    skip: int = Query(default=0, ge=0),
    limit: int = Query(default=20, ge=1, le=100),
    db: Session = Depends(get_db),
    user: User = Depends(require_employer),
):
    count_map: dict[int, int] = {}
    for candidate in visible_candidates(db):
        if candidate.category_id is None:
            continue
        count_map[candidate.category_id] = count_map.get(candidate.category_id, 0) + 1
    query = db.query(Category)
    if specialization is not None:
        query = query.filter(Category.specialization == specialization.strip().lower())
    if grade is not None:
        query = query.filter(Category.grade == grade.strip().lower())
    if q is not None and q.strip():
        needle = f"%{q.strip().lower()}%"
        query = query.filter(or_(Category.specialization.ilike(needle), Category.grade.ilike(needle)))
    total = query.count()
    categories = query.order_by(Category.specialization, Category.grade).offset(skip).limit(limit).all()
    return CategoryPage(
        total=total,
        items=[
            CategoryResponse(
                id=category.id,
                specialization=category.specialization,
                grade=category.grade,
                candidate_count=count_map.get(category.id, 0),
            )
            for category in categories
        ],
    )
