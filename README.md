# KPi-Tech Job Board — AI-Powered Candidate Matching

A full-stack job board with two roles (Company Admin and Candidate) and an AI matching
engine that takes a natural-language description of the role someone wants, ranks the
currently-open listings against it, and explains why each result matched.

Built as the hiring assessment for the **AI Software Engineer** role at KPi-Tech Services Inc.

---

## Contents

- [Quick start](#quick-start)
- [Tech stack](#tech-stack)
- [Architecture](#architecture)
- [How the AI matching works](#how-the-ai-matching-works)
- [API reference](#api-reference)
- [Project structure](#project-structure)
- [Architecture decisions](#architecture-decisions)
- [Assumptions](#assumptions)
- [Testing](#testing)
- [Known limitations and what I would do next](#known-limitations-and-what-i-would-do-next)

---

## Quick start

**Prerequisites:** Python 3.11+ and Node.js 18+.

### 1. Backend

```bash
cd backend

python -m venv .venv
# Windows
.venv\Scripts\activate
# macOS / Linux
source .venv/bin/activate

pip install -r requirements.txt

# Create the SQLite database and load demo data
python -m app.seed --reset

# Run the API on http://127.0.0.1:8000
uvicorn app.main:app --reload
```

Interactive API docs: <http://127.0.0.1:8000/docs>

### 2. Frontend

In a second terminal:

```bash
cd frontend
npm install
npm run dev
```

Open <http://localhost:5173>.

Vite proxies `/api` to the backend, so the browser only ever talks to one origin
and CORS never enters the picture during development.

### 3. Sign in

Every demo account uses the password **`Password123`**.

| Role | Email | Notes |
|---|---|---|
| Company Admin | `admin@medicore.io` | MediCore Health — healthcare startup, 6 listings |
| Company Admin | `admin@finstack.io` | FinStack Labs — fintech, 7 listings |
| Candidate | `sana.k@example.com` | Python backend, 3 yrs |
| Candidate | `rahul.d@example.com` | ML / NLP, 4 yrs |
| Candidate | `meera.n@example.com` | React frontend, 5 yrs |
| Candidate | `vikram.s@example.com` | DevOps, 7 yrs |
| Candidate | `ananya.g@example.com` | Fresh graduate |
| Candidate | `imran.q@example.com` | Full stack, 4 yrs |

The login screen has one-click buttons that fill these in.

---

## Tech stack

| Layer | Choice | Why |
|---|---|---|
| Backend | **Python + FastAPI** | The brief allows Flask or FastAPI. FastAPI gives request/response validation from type hints and generates OpenAPI docs for free, which made the API self-documenting during the build. |
| ORM / DB | **SQLAlchemy 2.0 + SQLite** | Zero-setup database — the grader clones the repo and runs one command. The SQLAlchemy layer means moving to PostgreSQL is a connection-string change. |
| Validation | **Pydantic v2** | Schemas are the API contract, kept separate from the ORM models so the database can change shape without silently changing what clients receive. |
| Auth | **JWT (PyJWT) + PBKDF2-HMAC-SHA256** | Stateless tokens; passwords salted per user with 260,000 iterations using only the standard library. |
| AI matching | **Custom TF-IDF + rule ensemble (no external ML deps)** | See [How the AI matching works](#how-the-ai-matching-works). |
| Frontend | **React 18 + Vite + React Router** | The brief requires React. Vite for instant dev startup; hand-written CSS rather than a component library. |
| Tests | **pytest** | 17 tests covering the matching engine — the part with real logic. |

**Runtime dependencies: 8 Python packages, 3 npm packages.** No ML framework, no CSS
framework, no external API key required.

---

## Architecture

```
┌────────────────────────────────────────────────────────────┐
│  React SPA (Vite, :5173)                                   │
│                                                            │
│  Auth context ── JWT in localStorage                       │
│  Router ── role-gated: /admin/*  vs  /match, /jobs, ...    │
│                                                            │
│  Admin views            Candidate views                    │
│  • Dashboard            • AI Match                         │
│  • My Job Listings      • Browse Jobs                      │
│  • Post / Edit Job      • My Applications                  │
│  • Job Applicants       • My Profile                       │
└───────────────────────────┬────────────────────────────────┘
                            │  /api/*  (Vite dev proxy)
                            ▼
┌────────────────────────────────────────────────────────────┐
│  FastAPI (:8000)                                           │
│                                                            │
│  Routers    auth · jobs · candidates · applications        │
│             match · dashboard                              │
│  Deps       get_current_user / get_current_admin /         │
│             get_current_candidate / get_optional_user      │
│  Schemas    Pydantic request + response models             │
│                                                            │
│  ┌──────────── app/matching/ ────────────────────────────┐ │
│  │  taxonomy.py  vocabulary (skills, domains, ...)       │ │
│  │  text.py      tokenizer, stopwords, bigrams           │ │
│  │  tfidf.py     TF-IDF vectoriser + cosine similarity   │ │
│  │  parser.py    natural language → structured Intent    │ │
│  │  engine.py    7-signal scoring + explanation builder  │ │
│  └───────────────────────────────────────────────────────┘ │
└───────────────────────────┬────────────────────────────────┘
                            ▼
                  SQLAlchemy ORM → SQLite
     users · candidate_profiles · jobs · applications
```

### End-to-end workflow — the AI matching path

```
Candidate types:  "I want a Python backend role in a startup that does healthcare"
        │
        ▼
POST /api/match  { query, limit, use_profile }
        │
        ▼
parse_query()  ── alias matching against taxonomy.py
        │        skills=[Python] role=[Backend] domain=[Healthcare] stage=[startup]
        ▼
enrich_with_profile()  ── optional: fill gaps from the saved profile
        │                 (query always wins; profile only fills what was left blank)
        ▼
SELECT jobs WHERE status = 'open'
        │
        ▼
rank_jobs()
        │
        ├── build TF-IDF index over all open job documents
        ├── for each job, score 7 signals ──┐
        │                                   │  semantic     0.25
        │                                   │  skills       0.25
        │                                   │  role_type    0.15
        │                                   │  domain       0.15
        │                                   │  location     0.10
        │                                   │  experience   0.07
        │                                   │  company_stage 0.03
        ├── weighted mean over ACTIVE signals only ◄────────┘
        ├── build human-readable reasons from the breakdown
        └── sort desc, drop noise below 15%
        │
        ▼
Response: ranked jobs + score + explanation + reasons + per-signal breakdown
          + what the parser understood (shown in the UI)
```

---

## How the AI matching works

The brief asks for natural-language matching with ranked results and an explanation
per result. The engine has three layers.

### Layer 1 — Intent parsing (`matching/parser.py`)

Alias matching against a hand-built taxonomy turns free text into a structured `Intent`:

```
"I want a Python backend role in a startup that does healthcare"
  → skills          ["Python"]
    role_types      ["Backend"]
    domains         ["Healthcare"]
    company_stages  ["startup"]
```

The taxonomy (`matching/taxonomy.py`) maps ~70 canonical skills, 17 business domains,
13 role types, 10 locations, plus work modes, company stages and seniority levels onto
the surface forms people actually type — `js` → JavaScript, `k8s` → Kubernetes,
`healthtech` → Healthcare, `wfh` → remote.

Aliases are sorted longest-first and consumed once matched, so `react native` registers
as **React Native** and does not also fire the bare `react` alias. There is a test
pinning exactly that.

### Layer 2 — TF-IDF similarity (`matching/tfidf.py`)

A ~60-line TF-IDF vectoriser written from scratch, over unigrams **and** bigrams so
`machine learning` is one feature rather than two:

```
tf(t,d) = count(t in d) / len(d)
idf(t)  = ln((1 + N) / (1 + df(t))) + 1      # smoothed, never zero
vector  = tf × idf, L2-normalised
score   = cosine similarity
```

The tokenizer deliberately keeps `+ # . / -` inside words so `c++`, `c#`, `node.js`,
`ci/cd` and `scikit-learn` survive as single tokens.

This layer is what catches phrasing the taxonomy has never seen — it provides recall
where the exact signals provide precision.

### Layer 3 — Weighted ensemble (`matching/engine.py`)

Seven signals, each normalised to 0–1:

| Signal | Weight | What it measures |
|---|---|---|
| `semantic` | 0.25 | TF-IDF cosine between query and job document |
| `skills` | 0.25 | `0.70 × recall + 0.30 × coverage` of the skill overlap |
| `role_type` | 0.15 | Backend / frontend / data science / …, inferred from the job title |
| `domain` | 0.15 | Healthcare / fintech / …, with partial credit from the description |
| `location` | 0.10 | City match, with remote treated as satisfying most city preferences |
| `experience` | 0.07 | Distance between seniority bands, plus years-vs-band fit |
| `company_stage` | 0.03 | Startup / midsize / enterprise, with adjacent stages partially credited |

**Signals the query never mentioned are switched off and their weight is redistributed.**
Without this, asking "remote Python job" would silently penalise every listing for not
matching a domain the candidate never named.

#### Why an ensemble rather than one model

Each signal fails differently. TF-IDF alone matches on vocabulary and will happily rank
a Python job in Mumbai above one in the candidate's own city. Exact filters alone are
brittle and return nothing when the phrasing is unusual. Blending them means the exact
signals give precision and the fuzzy one gives recall.

#### The behaviour that proves it is not keyword search

The seed data contains two listings with **the same title and the same required skills**,
differing only in domain and company stage. For the brief's own example query:

| Job | Domain / stage | Score |
|---|---|---|
| Python Backend Engineer — MediCore | Healthcare / startup | **75%** |
| Senior Backend Engineer — MediCore | Healthcare / startup | **72%** |
| Python Backend Engineer, Payments — FinStack | Fintech / midsize | **52%** |
| QA Automation Engineer — MediCore | Healthcare / startup | **51%** |

An exact title match drops 23 points because the domain and stage are wrong, and a
healthcare-startup role drops because it is not a backend role. This is pinned by
`test_domain_and_stage_outrank_an_identical_title` and
`test_role_type_outranks_domain_alone`.

### Explanations

Explanations are generated from the numeric breakdown, so they can never disagree with
the score. Each result returns a headline, bullet-point reasons, matched skills, gap
skills, and the full per-signal breakdown — which the UI renders as bars, so the
ranking is inspectable rather than a black box.

### Why not an LLM?

A hosted LLM would handle novel phrasing better. I chose a deterministic engine because:

1. **It cannot fail during a live demo** — no API key, no network, no rate limit, no latency.
2. **Every number is explainable.** In an interview about an AI feature, being able to
   point at the exact IDF term that produced a score is worth more than "the model said 0.62".
3. **It is reproducible** — the same query always returns the same ranking, which makes
   the behaviour testable.

The honest trade-off is stated in [Known limitations](#known-limitations-and-what-i-would-do-next),
along with how I would add an LLM layer without giving up the guarantees above.

---

## API reference

All endpoints are under `/api`. Full interactive docs at `/docs` when the server is running.

### Auth
| Method | Path | Auth | Description |
|---|---|---|---|
| `POST` | `/auth/register` | — | Create an account, returns a token |
| `POST` | `/auth/login` | — | Sign in, returns a token |
| `GET` | `/auth/me` | Any | Current user |

### Jobs
| Method | Path | Auth | Description |
|---|---|---|---|
| `GET` | `/jobs` | — | List/search. Filters: `q`, `skills`, `location`, `experience_level`, `work_mode`, `domain`, `status`, `limit`, `offset` |
| `GET` | `/jobs/{id}` | — | Single job |
| `POST` | `/jobs` | Admin | Create |
| `PUT` | `/jobs/{id}` | Admin (owner) | Update |
| `PATCH` | `/jobs/{id}/status` | Admin (owner) | Open / close |
| `DELETE` | `/jobs/{id}` | Admin (owner) | Delete |

### Candidate profile
| Method | Path | Auth | Description |
|---|---|---|---|
| `GET` | `/candidates/me/profile` | Candidate | Own profile |
| `PUT` | `/candidates/me/profile` | Candidate | Create or replace |
| `GET` | `/candidates/{id}/profile` | Admin | An applicant's live profile |

### Applications
| Method | Path | Auth | Description |
|---|---|---|---|
| `POST` | `/applications` | Candidate | Apply (snapshots the profile) |
| `GET` | `/applications/me` | Candidate | Own applications with job details |
| `GET` | `/applications/job/{id}` | Admin (owner) | Applicants for a job, filterable by `status` |
| `PATCH` | `/applications/{id}/status` | Admin (owner) | Applied → Shortlisted → Rejected |
| `DELETE` | `/applications/{id}` | Candidate (own) | Withdraw |

### AI matching and dashboard
| Method | Path | Auth | Description |
|---|---|---|---|
| `POST` | `/match` | Optional | Rank open jobs against a natural-language query |
| `GET` | `/dashboard` | Admin | Applications per job, skill distribution, pipeline counts |
| `GET` | `/health` | — | Liveness probe |

### Status codes

`200` OK · `201` Created · `400` bad request (e.g. applying to a closed job) ·
`401` missing/invalid token · `403` wrong role or not the owner · `404` not found ·
`409` conflict (duplicate email, duplicate application) · `422` validation failure.

Every error response has the same shape: `{"detail": "..."}`.

---

## Project structure

```
kpitech-hiring-assesment-ai/
├── README.md
├── DEVELOPMENT_LOG.md          ← how the project was built, phase by phase
├── .gitignore
│
├── backend/
│   ├── requirements.txt
│   ├── requirements-dev.txt
│   ├── .env.example
│   ├── app/
│   │   ├── main.py             FastAPI app, CORS, error handlers
│   │   ├── config.py           settings with working defaults
│   │   ├── database.py         engine, session factory, get_db dependency
│   │   ├── models.py           SQLAlchemy ORM models + enums
│   │   ├── schemas.py          Pydantic request/response contract
│   │   ├── security.py         PBKDF2 hashing, JWT issue/verify
│   │   ├── deps.py             current-user resolution + role guards
│   │   ├── seed.py             demo data
│   │   ├── matching/
│   │   │   ├── taxonomy.py     skills / domains / roles / locations vocabulary
│   │   │   ├── text.py         tokenizer, stopwords, bigrams
│   │   │   ├── tfidf.py        TF-IDF vectoriser + cosine similarity
│   │   │   ├── parser.py       natural language → Intent
│   │   │   └── engine.py       7-signal scoring + explanations
│   │   └── routers/
│   │       ├── auth.py  jobs.py  candidates.py
│   │       ├── applications.py  matching.py  dashboard.py
│   └── tests/
│       └── test_matching.py    17 tests
│
└── frontend/
    ├── package.json  vite.config.js  index.html
    └── src/
        ├── main.jsx  App.jsx  api.js  auth.jsx  styles.css
        ├── components/  Layout.jsx  ui.jsx  JobDetails.jsx
        └── pages/
            ├── Login.jsx  Register.jsx
            ├── admin/      Dashboard.jsx  JobsList.jsx  JobForm.jsx  JobApplicants.jsx
            └── candidate/  AiMatch.jsx  BrowseJobs.jsx  MyApplications.jsx  Profile.jsx
```

---

## Architecture decisions

**Schemas separate from ORM models.** Pydantic schemas are the API contract; SQLAlchemy
models are storage. Keeping them apart means a database change cannot silently alter what
clients receive.

**Applications store a profile snapshot.** The brief says an application "includes the
candidate's profile details". Storing a frozen copy at apply time means an admin reviewing
a three-week-old application sees what was actually submitted — and the dashboard's skill
distribution answers "what skills did our applicants have?" without changing retroactively
when someone edits their profile.

**Extra job fields beyond the minimum.** The brief's example query names a **domain**
("healthcare") and a **company stage** ("startup"). Without columns for those, the matcher
would have to infer both from free text. I added `domain`, `company_stage`, `work_mode`,
`company_name` and `min_years_experience` — all optional, all directly consumed by a
scoring signal.

**Ownership checks, not just role checks.** Being an admin is not enough to edit a listing;
`_get_own_job` asserts `job.created_by == admin.id`. Two companies can use the same instance
without seeing each other's data.

**Matching is public, and richer when signed in.** `POST /match` works anonymously so the
feature can be demoed without a login. When a candidate is signed in and opts in, their
profile fills gaps the query left blank — but the query always wins, so typing "I want a
frontend role" with a backend-heavy profile still returns frontend jobs.

**Errors are normalised.** A `RequestValidationError` handler flattens Pydantic's nested
error list into one readable sentence, so every error the frontend sees is `{"detail": "..."}`
and can be rendered directly.

**Role gating in the router.** Page components never check permissions — they can assume they
would not have rendered otherwise. The backend enforces the same rules independently; the
frontend layer is UX, not security.

**Hand-written CSS.** ~400 lines I can explain, instead of a dependency I would have to justify.

---

## Assumptions

1. **One admin account represents one company.** There is no organisation entity, so an admin
   sees only listings they personally created. A real system would add an `Organisation` table
   so colleagues share a job pool.
2. **A candidate has exactly one profile**, created automatically at registration so the
   frontend never handles a "profile does not exist yet" state.
3. **A candidate may apply to a job once** — enforced by a unique constraint on
   `(job_id, candidate_id)`, surfaced as `409`.
4. **Only open listings are matched or applied to.** The brief says matching works over "what
   is currently posted"; surfacing a closed listing would waste the candidate's time.
5. **Pipeline transitions are unrestricted between the three states.** An admin can move an
   application back to Applied or un-reject someone. Only the three named statuses are valid.
6. **Seniority bands** are entry 0–2 yrs, mid 2–5, senior 5–9, lead 8+. Used to score how well
   stated experience lines up with a listing.
7. **Locations are Indian metros plus "Remote"**, matching the seed dataset. Adding a city is a
   one-line change in `taxonomy.py`.
8. **The demo password is shared and printed on screen.** Convenience for review only; no real
   deployment would do this.
9. **`create_all()` on startup instead of migrations.** Correct for a project of this size;
   Alembic is the production answer.

---

## Testing

```bash
cd backend
pip install -r requirements-dev.txt
pytest tests -q
```

**17 tests, all passing.** They target the matching engine — the part with real logic and real
judgement calls — rather than CRUD endpoints that are mostly framework plumbing. Each test
states a behaviour worth defending:

- the brief's example query decomposes into all four signals
- aliases resolve (`js` → JavaScript, `healthtech` → Healthcare, `wfh` → remote)
- `react native` does not also register as `React`
- multi-word tokens (`node.js`, `ci/cd`, `c#`) survive tokenisation
- an unrecognised query returns an empty intent rather than guessing
- **domain and company stage outrank an identical job title**
- **role type outranks domain alone**
- signals the query never mentioned do not penalise a job
- every result carries a non-empty explanation

The full feature set was additionally verified end-to-end against the running API —
55 checks covering auth and role guards, job CRUD and ownership, search and filtering,
profiles, the AI matcher, the application pipeline, dashboard aggregates and error codes.

---

## Known limitations and what I would do next

**Where the matcher is weakest.** The parser only understands vocabulary in `taxonomy.py`.
A genuinely novel phrasing — an unlisted skill, a domain I did not anticipate — falls through
to the TF-IDF layer, which handles it but with less precision. The vocabulary is also
English-only and India-centric on locations.

**What I would build next, in priority order:**

1. **Sentence embeddings as an eighth signal.** Encode the query and each job document with a
   sentence-transformer, cache the job vectors, and blend cosine similarity in alongside TF-IDF.
   That fixes the vocabulary ceiling — "I want to work on models that read doctors' notes"
   would match a clinical-NLP role without ever naming a listed skill.
2. **An LLM re-ranker over the top N, behind a feature flag.** Keep the deterministic engine as
   the always-on path, then re-rank the top ~10 with an LLM and use it to write richer
   explanations. Falling back to the current output if the call fails or times out keeps the
   demo-safety property while gaining the quality.
3. **Learn the weights instead of hand-tuning them.** The seven weights are currently my
   judgement. With real click and application data, logistic regression on "did this candidate
   apply?" would replace guesses with evidence.
4. **Normalise skills into their own table** so they can be indexed, deduplicated globally, and
   filtered in SQL rather than in Python.
5. **Alembic migrations**, PostgreSQL, refresh tokens and rate limiting before any real deployment.
6. **Frontend tests.** The backend has 17; the React layer currently has none.

**Smaller known gaps:** no pagination UI (the API supports `limit`/`offset`); no email
notifications on status change; no resume/file upload; no full-text search index, so keyword
search is a `LIKE` scan that would need Postgres full-text or Elasticsearch at scale.
