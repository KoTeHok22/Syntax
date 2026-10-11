from fastapi.testclient import TestClient

from tests.test_api import auth, register_and_login
from tests.test_candidate_detail import seed_candidate


def seed_achievements(candidate_id: int, rows: list[dict]) -> None:
    from datetime import date

    from backend.db import SessionLocal
    from backend.models import PvnAchievement

    db = SessionLocal()
    try:
        for row in rows:
            db.add(
                PvnAchievement(
                    candidate_profile_id=candidate_id,
                    achievement_type=row["type"],
                    level=row["level"],
                    achieved_at=row.get("achieved_at", date(2026, 3, 14)),
                    score=row.get("score", 40.0),
                    source_issuer=row.get("source_issuer", "Лига Уникальных Соревнований"),
                )
            )
        db.commit()
    finally:
        db.close()


def detail(client: TestClient, email: str, achievements: list[dict]) -> tuple[dict, str]:
    register_and_login(client, email, "candidate")
    candidate_id = seed_candidate(email, "Группировка Достижений", ["python"])
    seed_achievements(candidate_id, achievements)
    employer_token = register_and_login(client, f"emp-{email}", "employer")
    response = client.get(f"/employer/candidates/{candidate_id}", headers=auth(employer_token))
    assert response.status_code == 200
    return response.json(), response.text


def test_identical_achievements_collapse_to_single_row(client: TestClient):
    body, _ = detail(
        client,
        "group-identical@example.com",
        [
            {"type": "хакатон", "level": "финалист"},
            {"type": "хакатон", "level": "финалист"},
            {"type": "хакатон", "level": "финалист"},
        ],
    )
    assert body["pvn_achievements"] == [{"type": "хакатон", "level": "финалист", "count": 3}]


def test_distinct_achievements_stay_separate(client: TestClient):
    body, _ = detail(
        client,
        "group-distinct@example.com",
        [
            {"type": "хакатон", "level": "финалист"},
            {"type": "хакатон", "level": "победитель"},
            {"type": "олимпиада", "level": "призёр"},
        ],
    )
    got = {(item["type"], item["level"]): item["count"] for item in body["pvn_achievements"]}
    assert got == {
        ("хакатон", "финалист"): 1,
        ("хакатон", "победитель"): 1,
        ("олимпиада", "призёр"): 1,
    }
    assert len(body["pvn_achievements"]) == 3


def test_grouping_order_is_deterministic(client: TestClient):
    rows = [
        {"type": "стажировка", "level": "junior"},
        {"type": "хакатон", "level": "финалист"},
        {"type": "хакатон", "level": "финалист"},
        {"type": "хакатон", "level": "финалист"},
        {"type": "олимпиада", "level": "призёр"},
        {"type": "олимпиада", "level": "призёр"},
    ]
    body, _ = detail(client, "group-order@example.com", rows)
    got = [(item["type"], item["level"], item["count"]) for item in body["pvn_achievements"]]
    assert got == [
        ("хакатон", "финалист", 3),
        ("олимпиада", "призёр", 2),
        ("стажировка", "junior", 1),
    ]


def test_achievements_never_expose_date_or_score(client: TestClient):
    body, text = detail(
        client,
        "group-privacy@example.com",
        [
            {"type": "хакатон", "level": "финалист", "score": 55.0},
            {"type": "хакатон", "level": "финалист", "score": 55.0},
        ],
    )
    for item in body["pvn_achievements"]:
        assert set(item) == {"type", "level", "count"}
        assert "date" not in item
        assert "score" not in item
    assert "40.0" not in text
    assert "55.0" not in text
