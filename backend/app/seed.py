"""Seed the database with demo data.

Run with:  python -m app.seed          (add --reset to wipe first)

The dataset is built so the AI matcher has something meaningful to discriminate
between. In particular it contains several Python backend roles that differ
only by domain and company stage, so the brief's example query - "I want a
Python backend role in a startup that does healthcare" - has to actually reason
rather than just keyword-match its way to one obvious answer.
"""

import argparse

from sqlalchemy import select

from app.database import Base, SessionLocal, engine
from app.models import (
    Application,
    ApplicationStatus,
    CandidateProfile,
    Job,
    User,
    UserRole,
)
from app.security import hash_password

DEMO_PASSWORD = "Password123"


ADMINS = [
    {
        "email": "admin@medicore.io",
        "full_name": "Priya Raghavan",
        "company_name": "MediCore Health",
    },
    {
        "email": "admin@finstack.io",
        "full_name": "Arjun Mehta",
        "company_name": "FinStack Labs",
    },
]


# owner_index points at ADMINS above.
JOBS = [
    {
        "owner_index": 0,
        "title": "Python Backend Engineer",
        "company_name": "MediCore Health",
        "domain": "Healthcare",
        "location": "Hyderabad",
        "work_mode": "hybrid",
        "company_stage": "startup",
        "experience_level": "mid",
        "min_years_experience": 2,
        "required_skills": ["Python", "FastAPI", "PostgreSQL", "Docker", "REST APIs"],
        "description": (
            "MediCore is an eleven-person team building the clinical data layer that hospitals "
            "use to move patient records between systems. You will own services that ingest HL7 "
            "and FHIR feeds, normalise them, and expose them over a versioned REST API. "
            "Expect to write a lot of Python, argue about schema design, and talk directly to the "
            "clinicians who use what you ship. We are pre-Series-A, so you will also help decide "
            "what we build next."
        ),
    },
    {
        "owner_index": 0,
        "title": "Senior Backend Engineer, Patient Platform",
        "company_name": "MediCore Health",
        "domain": "Healthcare",
        "location": "Remote",
        "work_mode": "remote",
        "company_stage": "startup",
        "experience_level": "senior",
        "min_years_experience": 5,
        "required_skills": ["Python", "Django", "PostgreSQL", "AWS", "Microservices", "Kubernetes"],
        "description": (
            "Lead the backend of our patient-facing platform. You will break a growing Django "
            "monolith into services, own the AWS footprint, and set the engineering bar for the "
            "team as we scale past our first hundred hospital customers. HIPAA compliance is part "
            "of the job, not an afterthought."
        ),
    },
    {
        "owner_index": 0,
        "title": "Machine Learning Engineer, Clinical NLP",
        "company_name": "MediCore Health",
        "domain": "Healthcare",
        "location": "Bengaluru",
        "work_mode": "hybrid",
        "company_stage": "startup",
        "experience_level": "mid",
        "min_years_experience": 3,
        "required_skills": ["Python", "NLP", "PyTorch", "LLMs", "Machine Learning", "Pandas"],
        "description": (
            "Build models that read unstructured clinical notes and pull out diagnoses, "
            "medications and follow-up actions. You will work with transformer models, fine-tune "
            "on de-identified data, and be responsible for the evaluation harness that tells us "
            "whether a model is safe to ship. Strong Python and a healthy scepticism about "
            "benchmark numbers required."
        ),
    },
    {
        "owner_index": 0,
        "title": "Frontend Engineer, Clinician Dashboard",
        "company_name": "MediCore Health",
        "domain": "Healthcare",
        "location": "Hyderabad",
        "work_mode": "onsite",
        "company_stage": "startup",
        "experience_level": "mid",
        "min_years_experience": 2,
        "required_skills": ["React", "TypeScript", "HTML/CSS", "REST APIs", "Testing"],
        "description": (
            "Own the interface doctors stare at for eight hours a day. This is React and "
            "TypeScript work where information density and keyboard speed matter more than "
            "animation. You will sit with clinicians, watch them work, and remove clicks."
        ),
    },
    {
        "owner_index": 1,
        "title": "Python Backend Engineer, Payments",
        "company_name": "FinStack Labs",
        "domain": "Fintech",
        "location": "Bengaluru",
        "work_mode": "hybrid",
        "company_stage": "midsize",
        "experience_level": "mid",
        "min_years_experience": 3,
        "required_skills": ["Python", "FastAPI", "PostgreSQL", "Redis", "REST APIs", "Testing"],
        "description": (
            "Work on the payments core that moves roughly two crore rupees a day. Idempotency, "
            "reconciliation and audit trails are the interesting problems here. You will write "
            "Python services, obsess over failure modes, and never be more than one alert away "
            "from finding out you were wrong."
        ),
    },
    {
        "owner_index": 1,
        "title": "Staff Backend Engineer, Core Ledger",
        "company_name": "FinStack Labs",
        "domain": "Fintech",
        "location": "Bengaluru",
        "work_mode": "hybrid",
        "company_stage": "midsize",
        "experience_level": "lead",
        "min_years_experience": 8,
        "required_skills": ["Go", "PostgreSQL", "Microservices", "Kubernetes", "gRPC", "Leadership"],
        "description": (
            "Set the direction for our double-entry ledger. This is a correctness-first system "
            "written mostly in Go. You will mentor four engineers, own the design review process, "
            "and be the person who says no when a change would compromise consistency."
        ),
    },
    {
        "owner_index": 1,
        "title": "Data Engineer",
        "company_name": "FinStack Labs",
        "domain": "Fintech",
        "location": "Pune",
        "work_mode": "remote",
        "company_stage": "midsize",
        "experience_level": "mid",
        "min_years_experience": 3,
        "required_skills": ["Python", "SQL", "Data Engineering", "AWS", "Docker"],
        "description": (
            "Build and run the pipelines that feed our risk models and regulatory reporting. "
            "Airflow, Spark and a lot of SQL. If a report is wrong at 6am, you are the person who "
            "can trace it back to the row that caused it."
        ),
    },
    {
        "owner_index": 1,
        "title": "Frontend Engineer, Merchant Console",
        "company_name": "FinStack Labs",
        "domain": "Fintech",
        "location": "Remote",
        "work_mode": "remote",
        "company_stage": "midsize",
        "experience_level": "senior",
        "min_years_experience": 5,
        "required_skills": ["React", "TypeScript", "Next.js", "HTML/CSS", "UI/UX"],
        "description": (
            "Own the console fifty thousand merchants use to manage settlements and disputes. "
            "React and Next.js, with real performance constraints - many of our merchants are on "
            "low-end Android devices over patchy connections."
        ),
    },
    {
        "owner_index": 1,
        "title": "Junior Python Developer",
        "company_name": "FinStack Labs",
        "domain": "Fintech",
        "location": "Chennai",
        "work_mode": "onsite",
        "company_stage": "midsize",
        "experience_level": "entry",
        "min_years_experience": 0,
        "required_skills": ["Python", "SQL", "Git", "REST APIs"],
        "description": (
            "A structured first engineering job. You will be paired with a senior engineer for "
            "your first six months, working on internal tooling and reporting services in Python. "
            "We care that you can read code and ask good questions, not that you already know our "
            "stack."
        ),
    },
    {
        "owner_index": 0,
        "title": "DevOps Engineer",
        "company_name": "MediCore Health",
        "domain": "Healthcare",
        "location": "Remote",
        "work_mode": "remote",
        "company_stage": "startup",
        "experience_level": "senior",
        "min_years_experience": 5,
        "required_skills": ["Kubernetes", "Terraform", "AWS", "CI/CD", "Docker", "Linux"],
        "description": (
            "You will be the first dedicated infrastructure hire. Today we deploy with a shell "
            "script and hope. You will replace that with Terraform, a real CI/CD pipeline and "
            "Kubernetes, while keeping an audited, compliant environment."
        ),
    },
    {
        "owner_index": 1,
        "title": "Full Stack Engineer",
        "company_name": "FinStack Labs",
        "domain": "Fintech",
        "location": "Hyderabad",
        "work_mode": "hybrid",
        "company_stage": "midsize",
        "experience_level": "mid",
        "min_years_experience": 3,
        "required_skills": ["Python", "React", "TypeScript", "PostgreSQL", "REST APIs", "Docker"],
        "description": (
            "Work across the stack on our internal operations tooling: FastAPI on the back, React "
            "on the front. Small team, short feedback loop, and the users sit two desks away."
        ),
    },
    {
        "owner_index": 0,
        "title": "QA Automation Engineer",
        "company_name": "MediCore Health",
        "domain": "Healthcare",
        "location": "Hyderabad",
        "work_mode": "onsite",
        "company_stage": "startup",
        "experience_level": "mid",
        "min_years_experience": 2,
        "required_skills": ["Testing", "Python", "CI/CD", "REST APIs", "Git"],
        "description": (
            "Build the automated test suite for a product where a bug can affect patient care. "
            "Python and pytest for API tests, plus browser automation for the clinician "
            "dashboard. You will own the release gate."
        ),
    },
    {
        "owner_index": 1,
        "title": "Product Manager, Lending",
        "company_name": "FinStack Labs",
        "domain": "Fintech",
        "location": "Mumbai",
        "work_mode": "hybrid",
        "company_stage": "midsize",
        "experience_level": "senior",
        "min_years_experience": 6,
        "required_skills": ["Product Management", "Data Analysis", "SQL", "Agile", "Communication"],
        "description": (
            "Own the lending product line end to end: from underwriting policy through to the "
            "borrower experience. You will work with data scientists on risk models and with "
            "compliance on what we are allowed to ship."
        ),
    },
    {
        "owner_index": 0,
        "title": "Backend Engineer, Data Platform (Closed)",
        "company_name": "MediCore Health",
        "domain": "Healthcare",
        "location": "Bengaluru",
        "work_mode": "hybrid",
        "company_stage": "startup",
        "experience_level": "senior",
        "min_years_experience": 5,
        "required_skills": ["Python", "SQL", "Data Engineering", "AWS"],
        "status": "closed",
        "description": (
            "This role has been filled. It is kept in the seed data so the closed-listing path, "
            "and the rule that AI matching only considers open jobs, are both demonstrable."
        ),
    },
]


CANDIDATES = [
    {
        "email": "sana.k@example.com",
        "full_name": "Sana Kulkarni",
        "headline": "Backend engineer, 3 years in Python + FastAPI",
        "skills": ["Python", "FastAPI", "PostgreSQL", "Docker", "REST APIs", "Git", "Testing"],
        "years_experience": 3,
        "preferred_location": "Hyderabad",
        "preferred_role_type": "Backend",
        "domain_interests": ["Healthcare", "Fintech"],
        "work_mode_preference": "hybrid",
        "education": [
            {"degree": "B.Tech, Computer Science", "institution": "NIT Warangal", "year": "2021"}
        ],
        "projects": [
            {
                "title": "Clinic appointment API",
                "summary": "FastAPI service handling slot booking and reminders for a two-clinic practice; ~800 bookings/month in production.",
                "tech": ["Python", "FastAPI", "PostgreSQL"],
            },
            {
                "title": "Invoice reconciliation tool",
                "summary": "Matched bank statements against invoices, cutting a two-day manual month-end task to about twenty minutes.",
                "tech": ["Python", "Pandas", "SQL"],
            },
        ],
    },
    {
        "email": "rahul.d@example.com",
        "full_name": "Rahul Desai",
        "headline": "ML engineer focused on NLP and applied LLMs",
        "skills": ["Python", "Machine Learning", "NLP", "PyTorch", "LLMs", "Pandas", "Docker"],
        "years_experience": 4,
        "preferred_location": "Bengaluru",
        "preferred_role_type": "Data Science",
        "domain_interests": ["Healthcare", "AI Research"],
        "work_mode_preference": "hybrid",
        "education": [
            {"degree": "M.Tech, Data Science", "institution": "IIT Hyderabad", "year": "2020"}
        ],
        "projects": [
            {
                "title": "Discharge summary extractor",
                "summary": "Fine-tuned a transformer to pull medication and follow-up instructions out of free-text discharge notes; 0.91 F1 on a held-out set.",
                "tech": ["Python", "PyTorch", "NLP"],
            }
        ],
    },
    {
        "email": "meera.n@example.com",
        "full_name": "Meera Nair",
        "headline": "Frontend engineer, React + TypeScript, 5 years",
        "skills": ["React", "TypeScript", "JavaScript", "HTML/CSS", "Next.js", "UI/UX", "Testing"],
        "years_experience": 5,
        "preferred_location": "Remote",
        "preferred_role_type": "Frontend",
        "domain_interests": ["Fintech", "E-commerce"],
        "work_mode_preference": "remote",
        "education": [
            {"degree": "B.E., Information Technology", "institution": "Anna University", "year": "2019"}
        ],
        "projects": [
            {
                "title": "Merchant analytics dashboard",
                "summary": "Rebuilt a slow reporting UI; first contentful paint went from 4.2s to 1.1s on a mid-range Android device.",
                "tech": ["React", "TypeScript", "Next.js"],
            }
        ],
    },
    {
        "email": "vikram.s@example.com",
        "full_name": "Vikram Shetty",
        "headline": "Platform / DevOps engineer, 7 years",
        "skills": ["Kubernetes", "Terraform", "AWS", "Docker", "CI/CD", "Linux", "Python"],
        "years_experience": 7,
        "preferred_location": "Remote",
        "preferred_role_type": "DevOps",
        "domain_interests": ["Healthcare", "SaaS"],
        "work_mode_preference": "remote",
        "education": [
            {"degree": "B.Tech, Electronics", "institution": "VIT Vellore", "year": "2017"}
        ],
        "projects": [
            {
                "title": "Zero-downtime migration to EKS",
                "summary": "Moved 40 services off EC2 onto EKS over six weeks with no customer-visible downtime.",
                "tech": ["Kubernetes", "Terraform", "AWS"],
            }
        ],
    },
    {
        "email": "ananya.g@example.com",
        "full_name": "Ananya Gupta",
        "headline": "Recent CS graduate looking for a first Python role",
        "skills": ["Python", "SQL", "Git", "HTML/CSS", "Flask"],
        "years_experience": 0.5,
        "preferred_location": "Chennai",
        "preferred_role_type": "Backend",
        "domain_interests": ["Fintech", "EdTech"],
        "work_mode_preference": "onsite",
        "education": [
            {"degree": "B.Sc., Computer Science", "institution": "Loyola College", "year": "2024"}
        ],
        "projects": [
            {
                "title": "Campus expense splitter",
                "summary": "Flask and SQLite app used by roughly 200 students in my hostel to split shared bills.",
                "tech": ["Python", "Flask", "SQL"],
            }
        ],
    },
    {
        "email": "imran.q@example.com",
        "full_name": "Imran Qureshi",
        "headline": "Full stack engineer, Python + React, 4 years",
        "skills": ["Python", "React", "TypeScript", "PostgreSQL", "Docker", "REST APIs", "AWS"],
        "years_experience": 4,
        "preferred_location": "Hyderabad",
        "preferred_role_type": "Full Stack",
        "domain_interests": ["Fintech", "SaaS"],
        "work_mode_preference": "hybrid",
        "education": [
            {"degree": "B.Tech, Computer Science", "institution": "JNTU Hyderabad", "year": "2020"}
        ],
        "projects": [
            {
                "title": "Internal ops console",
                "summary": "FastAPI backend and React frontend replacing a spreadsheet workflow used by a 25-person support team.",
                "tech": ["Python", "React", "PostgreSQL"],
            }
        ],
    },
]


# (candidate_email, job_title, status)
APPLICATIONS = [
    ("sana.k@example.com", "Python Backend Engineer", ApplicationStatus.SHORTLISTED),
    ("sana.k@example.com", "Full Stack Engineer", ApplicationStatus.APPLIED),
    ("sana.k@example.com", "Python Backend Engineer, Payments", ApplicationStatus.APPLIED),
    ("rahul.d@example.com", "Machine Learning Engineer, Clinical NLP", ApplicationStatus.SHORTLISTED),
    ("rahul.d@example.com", "Python Backend Engineer", ApplicationStatus.REJECTED),
    ("meera.n@example.com", "Frontend Engineer, Merchant Console", ApplicationStatus.SHORTLISTED),
    ("meera.n@example.com", "Frontend Engineer, Clinician Dashboard", ApplicationStatus.APPLIED),
    ("vikram.s@example.com", "DevOps Engineer", ApplicationStatus.SHORTLISTED),
    ("ananya.g@example.com", "Junior Python Developer", ApplicationStatus.APPLIED),
    ("ananya.g@example.com", "Python Backend Engineer", ApplicationStatus.REJECTED),
    ("imran.q@example.com", "Full Stack Engineer", ApplicationStatus.APPLIED),
    ("imran.q@example.com", "Python Backend Engineer, Payments", ApplicationStatus.SHORTLISTED),
]


def _make_user(email: str, full_name: str, role: UserRole, company_name: str | None = None) -> User:
    password_hash, salt = hash_password(DEMO_PASSWORD)
    return User(
        email=email,
        password_hash=password_hash,
        password_salt=salt,
        role=role.value,
        full_name=full_name,
        company_name=company_name,
    )


def seed(reset: bool = False) -> None:
    if reset:
        print("Dropping all tables...")
        Base.metadata.drop_all(bind=engine)

    Base.metadata.create_all(bind=engine)
    db = SessionLocal()

    try:
        if db.scalar(select(User).limit(1)) is not None:
            print("Database already contains data. Re-run with --reset to rebuild it.")
            return

        # --- admins --------------------------------------------------------
        admin_rows: list[User] = []
        for spec in ADMINS:
            admin = _make_user(spec["email"], spec["full_name"], UserRole.ADMIN, spec["company_name"])
            db.add(admin)
            admin_rows.append(admin)
        db.flush()

        # --- jobs ----------------------------------------------------------
        job_by_title: dict[str, Job] = {}
        for spec in JOBS:
            data = dict(spec)
            owner = admin_rows[data.pop("owner_index")]
            job = Job(**data, created_by=owner.id)
            db.add(job)
            job_by_title[job.title] = job
        db.flush()

        # --- candidates ----------------------------------------------------
        user_by_email: dict[str, User] = {}
        profile_by_email: dict[str, CandidateProfile] = {}
        for spec in CANDIDATES:
            user = _make_user(spec["email"], spec["full_name"], UserRole.CANDIDATE)
            db.add(user)
            db.flush()
            profile = CandidateProfile(
                user_id=user.id,
                full_name=spec["full_name"],
                headline=spec["headline"],
                skills=spec["skills"],
                education=spec["education"],
                projects=spec["projects"],
                years_experience=spec["years_experience"],
                preferred_location=spec["preferred_location"],
                preferred_role_type=spec["preferred_role_type"],
                domain_interests=spec["domain_interests"],
                work_mode_preference=spec["work_mode_preference"],
            )
            db.add(profile)
            user_by_email[spec["email"]] = user
            profile_by_email[spec["email"]] = profile
        db.flush()

        # --- applications --------------------------------------------------
        for email, job_title, app_status in APPLICATIONS:
            user = user_by_email[email]
            profile = profile_by_email[email]
            job = job_by_title[job_title]
            db.add(
                Application(
                    job_id=job.id,
                    candidate_id=user.id,
                    status=app_status.value,
                    cover_note=f"I'm interested in the {job.title} role at {job.company_name}.",
                    profile_snapshot={
                        "full_name": profile.full_name,
                        "email": user.email,
                        "headline": profile.headline,
                        "skills": profile.skills,
                        "education": profile.education,
                        "projects": profile.projects,
                        "years_experience": profile.years_experience,
                        "preferred_location": profile.preferred_location,
                        "preferred_role_type": profile.preferred_role_type,
                        "domain_interests": profile.domain_interests,
                        "work_mode_preference": profile.work_mode_preference,
                    },
                )
            )

        db.commit()

        print("Seed complete.")
        print(f"  {len(ADMINS)} admins, {len(JOBS)} jobs, {len(CANDIDATES)} candidates, "
              f"{len(APPLICATIONS)} applications")
        print(f"\n  Every demo account uses the password: {DEMO_PASSWORD}")
        print("\n  Admin logins:")
        for spec in ADMINS:
            print(f"    {spec['email']}  ({spec['company_name']})")
        print("\n  Candidate logins:")
        for spec in CANDIDATES:
            print(f"    {spec['email']}  ({spec['headline']})")
    finally:
        db.close()


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Seed the job board database.")
    parser.add_argument("--reset", action="store_true", help="Drop all tables before seeding.")
    args = parser.parse_args()
    seed(reset=args.reset)
