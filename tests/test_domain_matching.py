from backend.core.domain_matching import (
    canonical_key,
    domain_matches_candidate,
    nearest_domain,
    normalize,
    similarity,
    token_set,
)


class FakeDomain:
    def __init__(self, slug, title, aliases):
        self.slug = slug
        self.title = title
        self.aliases = aliases


DB_DOMAIN = FakeDomain(
    "databases",
    "Базы данных",
    ["база данных", "субд", "postgres", "postgresql", "sql", "хранилище данных", "dwh", "массив данных", "информационная система"],
)
ALGO_DOMAIN = FakeDomain(
    "algorithms",
    "Алгоритмы и структуры данных",
    ["алгоритмы", "структуры данных", "сложность алгоритмов"],
)


def test_normalize_lowercases_and_folds_yo():
    assert normalize("  База ЁЖ  ") == "база еж"


def test_canonical_key_strips_punctuation():
    assert canonical_key("Data Engineering") == "data-engineering"


def test_token_set_stems_russian_endings():
    stems = token_set("Базы данных")
    assert any(item.startswith("баз") for item in stems)
    assert any(item.startswith("данн") for item in stems)


def test_similarity_matches_synonym_terms():
    assert similarity("база данных", "хранилище данных") >= 0.6
    assert similarity("postgres", "postgresql") >= 0.55


def test_expected_synonyms_resolve_to_databases_domain():
    for query in ["база данных", "хранилище данных", "информационная система", "массив данных", "субд", "postgres"]:
        found = nearest_domain(query, [ALGO_DOMAIN, DB_DOMAIN])
        assert found is not None, f"не найдено для «{query}»"
        assert found.slug == "databases", f"«{query}» привёл к {found.slug}"


def test_unrelated_query_does_not_match():
    assert nearest_domain("менеджер по продажам", [ALGO_DOMAIN, DB_DOMAIN]) is None


def test_domain_matches_candidate_through_skills():
    assert domain_matches_candidate(DB_DOMAIN, "backend", ["django", "postgresql"]) is True
    assert domain_matches_candidate(DB_DOMAIN, "frontend", ["flutter", "dart"]) is False
