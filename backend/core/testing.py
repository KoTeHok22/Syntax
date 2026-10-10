from datetime import datetime, timedelta, timezone

VERDICT_CONFIRMED = "confirmed"
VERDICT_SUGGEST_HIGHER = "suggest_higher"
VERDICT_SUGGEST_LOWER = "suggest_lower"

GRADE_ORDER = {"junior": 0, "middle": 1, "senior": 2}
GRADE_NEXT = {"junior": "middle", "middle": "senior"}
GRADE_PREVIOUS = {"middle": "junior", "senior": "middle"}

GRADE_PASS_THRESHOLD = {"junior": 60, "middle": 75, "senior": 85}
GRADE_CONFIRMATION_VALID_MONTHS = 12

SESSION_STATUS_PENDING = "pending"
SESSION_STATUS_COMPLETED = "completed"


def pass_threshold(grade: str) -> int:
    return GRADE_PASS_THRESHOLD.get(grade, 60)


def adaptive_verdict(correct_count: int, task_count: int, grade: str | None = None) -> str:
    if task_count == 0:
        return VERDICT_SUGGEST_LOWER
    score = result_score(correct_count, task_count)
    threshold = pass_threshold(grade) if grade is not None else 80
    if score >= 95:
        return VERDICT_SUGGEST_HIGHER
    if score >= threshold:
        return VERDICT_CONFIRMED
    return VERDICT_SUGGEST_LOWER


def suggested_grade(grade: str, verdict: str) -> str | None:
    if verdict == VERDICT_SUGGEST_HIGHER:
        return GRADE_NEXT.get(grade)
    if verdict == VERDICT_SUGGEST_LOWER:
        return GRADE_PREVIOUS.get(grade)
    return None


def result_score(correct_count: int, task_count: int) -> int:
    if task_count == 0:
        return 0
    return round(100.0 * correct_count / task_count)


def grade_change_allowed(grade_changed_at: datetime | None, cooldown_months: int) -> bool:
    if grade_changed_at is None:
        return True
    changed_at = grade_changed_at if grade_changed_at.tzinfo else grade_changed_at.replace(tzinfo=timezone.utc)
    months_since = (datetime.now(timezone.utc) - changed_at).days / 30.44
    return months_since >= cooldown_months


def grade_confirmation_active(confirmed_at: datetime | None, valid_months: int = GRADE_CONFIRMATION_VALID_MONTHS) -> bool:
    if confirmed_at is None:
        return False
    moment = confirmed_at if confirmed_at.tzinfo else confirmed_at.replace(tzinfo=timezone.utc)
    months_since = (datetime.now(timezone.utc) - moment).days / 30.44
    return months_since < valid_months


def grade_confirmation_expires_at(confirmed_at: datetime | None, valid_months: int = GRADE_CONFIRMATION_VALID_MONTHS) -> datetime | None:
    if confirmed_at is None:
        return None
    moment = confirmed_at if confirmed_at.tzinfo else confirmed_at.replace(tzinfo=timezone.utc)
    return moment + timedelta(days=round(valid_months * 30.44))
