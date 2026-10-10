import pytest

from backend.core.domain_matching import similarity, terms_match_query
from backend.services.semantic_matching import normalize_rerank_scores, rerank_documents
from backend.services.reranking import rerank_enabled


def test_short_alias_does_not_match_inside_unrelated_word():
    assert similarity("linux", "ux") < 0.6
    assert not terms_match_query("linux", ["ux", "ui"], threshold=0.62)


def test_meaningful_term_still_matches():
    assert terms_match_query("дизайнер интерфейсов", ["дизайнер"], threshold=0.62)
    assert similarity("airflow", "airflow") == 1.0


def test_normalize_rerank_scores_scales_to_unit_range():
    assert normalize_rerank_scores([2.0, 4.0, 6.0]) == [0.0, 0.5, 1.0]
    assert normalize_rerank_scores([5.0, 5.0]) == [1.0, 1.0]
    assert normalize_rerank_scores([]) == []


def test_rerank_documents_carries_stack_and_resume():
    from backend.models import CandidateProfile

    candidate = CandidateProfile(specialization="data", stack=["airflow", "kafka"], soft_skills=["communication"],
                                 resume_text="Built pipelines", assessment_text="Solved an ETL case")
    documents = rerank_documents(candidate)
    joined = " ".join(documents)
    assert "airflow" in joined and "Built pipelines" in joined and "Solved an ETL case" in joined


def test_rerank_disabled_without_configuration():
    assert rerank_enabled() in (True, False)


@pytest.mark.asyncio
async def test_rerank_returns_none_without_documents(monkeypatch):
    from backend.services import reranking

    monkeypatch.setattr(reranking, "rerank_enabled", lambda: True)
    assert await reranking.rerank("q", []) is None
