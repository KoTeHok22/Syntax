from backend.api.routes.candidates import stack_matches


def test_any_selected_skill_matches():
    candidate = ["Python", "Django", "PostgreSQL"]
    assert stack_matches(candidate, ["Python", "Django"]) is True
    assert stack_matches(candidate, ["Python", "Kafka"]) is True
    assert stack_matches(["Python"], ["Python", "Django"]) is True
    assert stack_matches(["Django"], ["Python", "Django"]) is True


def test_no_overlap_is_excluded():
    assert stack_matches(["Python", "Django"], ["Kafka", "Redis"]) is False
    assert stack_matches(["Python"], ["Django"]) is False


def test_single_skill_matches():
    candidate = ["Python", "Django"]
    assert stack_matches(candidate, ["Python"]) is True
    assert stack_matches(candidate, ["Django"]) is True
    assert stack_matches(candidate, ["Kafka"]) is False


def test_match_is_case_insensitive():
    assert stack_matches(["PYTHON", "django"], ["python", "DJANGO"]) is True
    assert stack_matches(["python"], ["Python", "Django"]) is True


def test_empty_filter_passes_everyone():
    assert stack_matches(["Python"], []) is True
    assert stack_matches(["Python"], None) is True
    assert stack_matches([], []) is True


def test_multi_token_requirement_matches_either_token():
    assert stack_matches(["airflow", "kafka"], ["kafka airflow"]) is True
    assert stack_matches(["airflow"], ["kafka airflow"]) is True
    assert stack_matches(["kafka"], ["kafka airflow"]) is True
    assert stack_matches(["redis"], ["kafka airflow"]) is False
    assert stack_matches([], ["kafka airflow"]) is False
