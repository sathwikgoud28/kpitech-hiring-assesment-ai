"""Tests for the AI matching engine.

These are the tests that matter most in this project. The CRUD endpoints are
mostly framework plumbing; the matcher is the part with real logic and real
judgement calls, so it is the part worth pinning down.

Each test states a behaviour I would want to defend out loud, not just a value
that happens to be true today.
"""

from dataclasses import dataclass, field

import pytest

from app.matching.engine import infer_role_types, job_document, rank_jobs
from app.matching.parser import parse_query
from app.matching.tfidf import TfidfIndex


@dataclass
class FakeJob:
    """A stand-in for the ORM model so these tests need no database."""

    id: int
    title: str
    description: str
    required_skills: list[str] = field(default_factory=list)
    experience_level: str = "mid"
    location: str = "Hyderabad"
    status: str = "open"
    company_name: str = "Test Co"
    domain: str = ""
    work_mode: str = "onsite"
    company_stage: str = "midsize"
    min_years_experience: float = 0.0


# --------------------------------------------------------------------------- #
# Parser
# --------------------------------------------------------------------------- #
def test_parses_the_brief_example_query():
    """The example from the assignment must decompose into all four signals."""
    intent = parse_query("I want a Python backend role in a startup that does healthcare")

    assert "Python" in intent.skills
    assert "Backend" in intent.role_types
    assert "Healthcare" in intent.domains
    assert "startup" in intent.company_stages


def test_recognises_aliases_not_just_exact_names():
    """A candidate types 'js' and 'healthtech', not 'JavaScript' and 'Healthcare'."""
    intent = parse_query("react and js developer for a healthtech company, wfh")

    assert "JavaScript" in intent.skills
    assert "React" in intent.skills
    assert "Healthcare" in intent.domains
    assert "remote" in intent.work_modes


def test_longer_alias_wins_over_its_own_substring():
    """'react native' must not also register as a bare 'React' hit.

    This is the bug that alias-ordering exists to prevent: without it, one
    phrase produces two contradictory skills and the score is inflated.
    """
    intent = parse_query("react native developer")

    assert "React Native" in intent.skills
    assert "React" not in intent.skills


def test_numeric_years_imply_a_seniority_band():
    intent = parse_query("backend engineer with 6 years experience")

    assert intent.years_experience == 6
    assert "senior" in intent.experience_levels


def test_remote_counts_as_both_a_location_and_a_work_mode():
    intent = parse_query("remote python job")

    assert "Remote" in intent.locations
    assert "remote" in intent.work_modes


def test_unrecognised_query_returns_an_empty_intent_rather_than_guessing():
    """Vocabulary the taxonomy has never seen should fall through to TF-IDF,
    not produce a confidently wrong structured parse."""
    intent = parse_query("something entirely unrelated to any technology")

    assert intent.is_empty()


# --------------------------------------------------------------------------- #
# TF-IDF
# --------------------------------------------------------------------------- #
def test_cosine_similarity_is_higher_for_the_more_relevant_document():
    index = TfidfIndex(
        [
            "python fastapi backend engineer building rest apis",
            "graphic designer working in figma on brand identity",
        ]
    )
    query = index.vectorize_query("python backend api developer")

    assert index.similarity(query, 0) > index.similarity(query, 1)


def test_identical_text_scores_near_one():
    text = "python fastapi postgresql backend engineer"
    index = TfidfIndex([text])
    assert index.similarity(index.vectorize_query(text), 0) == pytest.approx(1.0, abs=0.01)


def test_multiword_tokens_survive_tokenisation():
    """'node.js' and 'ci/cd' must not be shredded into meaningless fragments."""
    index = TfidfIndex(["we use node.js and ci/cd pipelines with c# services"])
    terms = index.term_lists[0]

    assert "node.js" in terms
    assert "ci/cd" in terms
    assert "c#" in terms


# --------------------------------------------------------------------------- #
# Role inference
# --------------------------------------------------------------------------- #
def test_role_type_is_inferred_from_the_job_title():
    job = FakeJob(id=1, title="Senior Backend Engineer", description="Build services.")
    assert "Backend" in infer_role_types(job)


# --------------------------------------------------------------------------- #
# Ranking - the behaviours worth defending in the demo
# --------------------------------------------------------------------------- #
def _brief_example_corpus() -> list[FakeJob]:
    return [
        FakeJob(
            id=1,
            title="Python Backend Engineer",
            description="Build FastAPI services that move patient records between hospitals.",
            required_skills=["Python", "FastAPI", "PostgreSQL"],
            domain="Healthcare",
            company_stage="startup",
        ),
        FakeJob(
            id=2,
            title="Python Backend Engineer, Payments",
            description="Build FastAPI services for a payments core handling settlements.",
            required_skills=["Python", "FastAPI", "PostgreSQL"],
            domain="Fintech",
            company_stage="enterprise",
        ),
        FakeJob(
            id=3,
            title="Frontend Engineer",
            description="Build a React dashboard for clinicians in a hospital setting.",
            required_skills=["React", "TypeScript"],
            domain="Healthcare",
            company_stage="startup",
        ),
    ]


def test_domain_and_stage_outrank_an_identical_title():
    """The headline claim of the whole feature.

    Two listings have the *same* title and the *same* required skills. The only
    difference is domain and company stage. The matcher must prefer the one the
    candidate actually described - if it does not, it is keyword search wearing
    an AI label.
    """
    intent = parse_query("I want a Python backend role in a startup that does healthcare")
    results = rank_jobs(intent, _brief_example_corpus(), limit=3)

    assert results[0].job.id == 1
    healthcare_startup = next(r for r in results if r.job.id == 1)
    fintech_enterprise = next(r for r in results if r.job.id == 2)
    assert healthcare_startup.score > fintech_enterprise.score


def test_role_type_outranks_domain_alone():
    """A healthcare frontend job must not beat a healthcare backend job when the
    candidate asked for backend."""
    intent = parse_query("I want a Python backend role in a startup that does healthcare")
    results = rank_jobs(intent, _brief_example_corpus(), limit=3)

    backend = next(r for r in results if r.job.id == 1)
    frontend = next(r for r in results if r.job.id == 3)
    assert backend.score > frontend.score


def test_every_result_carries_a_human_readable_explanation():
    """The brief requires an explanation per result - assert it is never blank."""
    intent = parse_query("python backend healthcare startup")
    results = rank_jobs(intent, _brief_example_corpus(), limit=3)

    assert results
    for result in results:
        assert result.explanation.strip()
        assert result.reasons
        assert all(reason.strip() for reason in result.reasons)


def test_unmentioned_signals_do_not_penalise_a_job():
    """Asking only about skills must not drag scores down for the domain,
    location and seniority the candidate never mentioned."""
    intent = parse_query("python fastapi")
    results = rank_jobs(intent, _brief_example_corpus(), limit=3)

    # Both Python jobs should still score respectably despite the query naming
    # no domain, city, seniority or company stage.
    top = results[0]
    assert top.score >= 50
    assert top.breakdown["domain"] == 0.0  # inactive, not a penalty


def test_matched_and_missing_skills_are_reported():
    intent = parse_query("python developer")
    results = rank_jobs(intent, _brief_example_corpus(), limit=3)

    top = next(r for r in results if r.job.id in (1, 2))
    assert "Python" in top.matched_skills
    assert "FastAPI" in top.missing_skills


def test_empty_corpus_returns_no_results_instead_of_raising():
    intent = parse_query("python backend")
    assert rank_jobs(intent, [], limit=5) == []


def test_job_document_repeats_the_high_signal_fields():
    """Title/skills/domain are weighted by repetition - guard that on purpose."""
    job = FakeJob(id=1, title="Backend Engineer", description="body", domain="Healthcare")
    document = job_document(job)

    assert document.count("Backend Engineer") == 2
    assert document.count("Healthcare") == 2
