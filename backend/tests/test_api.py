"""API-level tests for behaviour that lives in the routers, not the engine.

`test_matching.py` covers the scoring logic in isolation. These tests cover the
rules that only exist once HTTP, auth and the database are involved - and in
particular the two guarantees that a purely engine-level test cannot check:

  * closed listings never reach the matcher
  * the LLM layer is strictly additive, so matching still works without a key

Each test builds its own in-memory database, so the suite never touches the
demo data and can run in any order.
"""

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.config import settings
from app.database import Base, get_db
from app.main import app

ADMIN = {"email": "admin@test.io", "password": "Password123", "full_name": "Test Admin",
         "role": "admin", "company_name": "TestCo"}
CANDIDATE = {"email": "cand@test.io", "password": "Password123", "full_name": "Test Candidate",
             "role": "candidate"}

JOB = {
    "title": "Python Backend Engineer",
    "description": "Build FastAPI services that move patient records between hospitals.",
    "required_skills": ["Python", "FastAPI", "PostgreSQL"],
    "experience_level": "mid",
    "location": "Hyderabad",
    "domain": "Healthcare",
    "company_stage": "startup",
    "work_mode": "hybrid",
}


@pytest.fixture()
def client():
    """A TestClient backed by a fresh in-memory database.

    StaticPool is required: without it every connection gets its own private
    in-memory database and the schema vanishes between requests.
    """
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(bind=engine)
    TestingSession = sessionmaker(bind=engine, autocommit=False, autoflush=False)

    def override_get_db():
        db = TestingSession()
        try:
            yield db
        finally:
            db.close()

    app.dependency_overrides[get_db] = override_get_db
    with TestClient(app) as test_client:
        yield test_client
    app.dependency_overrides.clear()


def token(client, payload) -> str:
    response = client.post("/api/auth/register", json=payload)
    assert response.status_code == 201, response.text
    return response.json()["access_token"]


def auth(tok: str) -> dict:
    return {"Authorization": f"Bearer {tok}"}


# --------------------------------------------------------------------------- #
# The regression this file exists for
# --------------------------------------------------------------------------- #
def test_closed_jobs_are_never_matched(client, monkeypatch):
    """A closed listing must not appear in AI matching results.

    This is the test whose absence let a stale demo database look like a bug.
    An assertion that merely checks "no closed job appeared" passes trivially
    when no closed job exists - so this test *creates* one and proves the
    matcher skips it while still returning the open one.
    """
    monkeypatch.setattr(settings, "groq_api_key", "")  # deterministic path only
    admin = token(client, ADMIN)

    open_job = client.post("/api/jobs", json=JOB, headers=auth(admin)).json()
    closed_job = client.post(
        "/api/jobs", json={**JOB, "title": "Python Backend Engineer, Archived"}, headers=auth(admin)
    ).json()

    closed = client.patch(
        f"/api/jobs/{closed_job['id']}/status?new_status=closed", headers=auth(admin)
    )
    assert closed.status_code == 200
    assert closed.json()["status"] == "closed"

    body = client.post(
        "/api/match", json={"query": "python backend healthcare startup", "limit": 20}
    ).json()

    returned = {result["job"]["id"] for result in body["results"]}
    assert closed_job["id"] not in returned, "a closed listing reached the matcher"
    assert open_job["id"] in returned, "the open listing should still be matched"
    assert body["total_open_jobs"] == 1


def test_closed_jobs_cannot_be_applied_to(client):
    admin = token(client, ADMIN)
    candidate = token(client, CANDIDATE)

    job = client.post("/api/jobs", json=JOB, headers=auth(admin)).json()
    client.patch(f"/api/jobs/{job['id']}/status?new_status=closed", headers=auth(admin))

    client.put(
        "/api/candidates/me/profile",
        json={"full_name": "Test Candidate", "skills": ["Python"], "years_experience": 3},
        headers=auth(candidate),
    )
    response = client.post("/api/applications", json={"job_id": job["id"]}, headers=auth(candidate))
    assert response.status_code == 400


# --------------------------------------------------------------------------- #
# The LLM layer must be strictly additive
# --------------------------------------------------------------------------- #
def test_matching_works_with_no_llm_key_configured(client, monkeypatch):
    """No API key must mean a normal, fully-populated deterministic response."""
    monkeypatch.setattr(settings, "groq_api_key", "")
    admin = token(client, ADMIN)
    client.post("/api/jobs", json=JOB, headers=auth(admin))

    body = client.post(
        "/api/match", json={"query": "python backend healthcare startup"}
    ).json()

    assert body["llm_available"] is False
    assert body["llm_used"] is False
    assert body["llm_model"] is None
    assert len(body["results"]) == 1
    # The deterministic engine still supplies everything the UI needs.
    assert body["results"][0]["explanation"]
    assert body["results"][0]["reasons"]
    assert body["results"][0]["breakdown"]["skills"] > 0


def test_llm_failure_falls_back_instead_of_erroring(client, monkeypatch):
    """A key that is present but broken must degrade, not 500."""
    monkeypatch.setattr(settings, "groq_api_key", "gsk_obviously-not-a-real-key")
    monkeypatch.setattr(settings, "groq_timeout_seconds", 3.0)
    admin = token(client, ADMIN)
    client.post("/api/jobs", json=JOB, headers=auth(admin))

    response = client.post("/api/match", json={"query": "python backend healthcare startup"})

    assert response.status_code == 200
    body = response.json()
    assert body["llm_available"] is True   # a key is configured...
    assert body["llm_used"] is False       # ...but the call failed, so we fell back
    assert len(body["results"]) == 1
    assert body["results"][0]["explanation"]


def test_use_llm_false_skips_the_llm_entirely(client, monkeypatch):
    monkeypatch.setattr(settings, "groq_api_key", "gsk_would-fail-if-called")
    admin = token(client, ADMIN)
    client.post("/api/jobs", json=JOB, headers=auth(admin))

    body = client.post(
        "/api/match", json={"query": "python backend", "use_llm": False}
    ).json()

    assert body["llm_used"] is False
    assert body["results"][0]["engine_score"] is None  # never blended


# --------------------------------------------------------------------------- #
# Role and ownership guards
# --------------------------------------------------------------------------- #
def test_candidate_cannot_create_a_job(client):
    candidate = token(client, CANDIDATE)
    response = client.post("/api/jobs", json=JOB, headers=auth(candidate))
    assert response.status_code == 403


def test_admin_cannot_edit_another_admins_job(client):
    admin_a = token(client, ADMIN)
    admin_b = token(client, {**ADMIN, "email": "other@test.io", "company_name": "OtherCo"})

    job = client.post("/api/jobs", json=JOB, headers=auth(admin_a)).json()
    response = client.put(
        f"/api/jobs/{job['id']}", json={"title": "Hijacked"}, headers=auth(admin_b)
    )
    assert response.status_code == 403


def test_duplicate_application_is_rejected(client):
    admin = token(client, ADMIN)
    candidate = token(client, CANDIDATE)
    job = client.post("/api/jobs", json=JOB, headers=auth(admin)).json()
    client.put(
        "/api/candidates/me/profile",
        json={"full_name": "Test Candidate", "skills": ["Python"], "years_experience": 3},
        headers=auth(candidate),
    )

    first = client.post("/api/applications", json={"job_id": job["id"]}, headers=auth(candidate))
    second = client.post("/api/applications", json={"job_id": job["id"]}, headers=auth(candidate))

    assert first.status_code == 201
    assert second.status_code == 409
