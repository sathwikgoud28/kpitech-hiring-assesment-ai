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
| AI matching | **Two-stage: custom TF-IDF ensemble → LLM re-rank** | Deterministic retrieval always runs; an LLM (Llama 3.3 via Groq) re-ranks the top results when a key is present. See [How the AI matching works](#how-the-ai-matching-works). |
| Frontend | **React 18 + Vite + React Router** | The brief requires React. Vite for instant dev startup; hand-written CSS rather than a component library. |
| Tests | **pytest** | 17 tests covering the matching engine — the part with real logic. |

**Runtime dependencies: 9 Python packages, 3 npm packages.** No ML framework, no CSS
framework. **An API key is optional** — without one the matcher runs entirely offline on
the deterministic engine.

### Optional: enabling the LLM layer

The application is fully functional with no API key. To enable LLM re-ranking:

1. Get a free key at [console.groq.com/keys](https://console.groq.com/keys)
2. `cp .env.example .env` in `backend/`, and set `GROQ_API_KEY=gsk_...`
3. Restart the API

With no key, `POST /api/match` returns `"llm_used": false` and the deterministic result.
Nothing errors and nothing is missing — the UI states which path ran.

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
│  │  engine.py    stage 1: 7-signal scoring + explanation │ │
│  │  llm.py       stage 2: LLM re-rank (optional) ────────┼─┼──▶ Groq
│  └───────────────────────────────────────────────────────┘ │    (Llama 3.3)
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
rank_jobs()                                    ── STAGE 1, always runs
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
llm.rerank(top 8)                              ── STAGE 2, optional
        │
        ├── no API key / error / timeout  ──▶  return stage 1 unchanged
        └── otherwise: LLM relevance + explanation per posting
                       score = 0.5 × stage 1 + 0.5 × stage 2, re-sorted
        │
        ▼
Response: ranked jobs + score + explanation + reasons + per-signal breakdown
          + engine_score / llm_relevance + llm_used + what the parser understood
```

---

## How the AI matching works

The brief asks for natural-language matching with ranked results and an explanation
per result. It works in **two stages** — the standard *retrieve-then-rerank* pattern.

```
                    ┌─────────────────────────────────────────────┐
   query    ───────▶│  STAGE 1  —  deterministic engine           │
                    │  parse intent → score every open job on     │
                    │  7 weighted signals → rank                  │
                    │  fast · offline · always runs               │
                    └──────────────────┬──────────────────────────┘
                                       │ top 8
                    ┌──────────────────▼──────────────────────────┐
                    │  STAGE 2  —  LLM re-rank        (optional)  │
                    │  Llama 3.3 70B via Groq re-scores and       │
                    │  re-explains the shortlist                  │
                    └──────────────────┬──────────────────────────┘
                                       │
              final score = 0.5 × stage 1  +  0.5 × stage 2
```

**Stage 2 is strictly additive.** No API key, network failure, rate limit, timeout, or
malformed response all return `None`, and the stage 1 result is served unchanged. The
feature cannot make the product worse than it is without it — which is what makes it
safe to demo live.

Stage 1 is described first because it is the part that always runs.

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

### Stage 2 — LLM re-rank (`matching/llm.py`)

The deterministic engine only understands vocabulary that exists in `taxonomy.py`. A
genuinely novel phrasing names no listed skill and no listed domain, so every structured
signal sits inactive and the ranking falls back to TF-IDF alone. That is a real ceiling,
and this stage is what removes it.

The top 8 results, the original query, and the parsed intent are sent to Llama 3.3 70B
(served by Groq) with a JSON-mode prompt. The model returns, per posting: a 0–100
relevance judgement, a one-sentence explanation, and 2–4 specific reasons.

**Measured effect.** For a query the taxonomy cannot parse at all:

> *"I want to build models that read doctors' handwritten notes"*
> — no listed skill, no listed domain, nothing for the structured signals to work with

| | Score for *Machine Learning Engineer, Clinical NLP* |
|---|---|
| Stage 1 only | **25.3%** — barely above the noise floor |
| Stage 1 + 2 | **60.1%** (engine 25.3, LLM 95) |

#### Why blend the scores rather than trust the LLM outright

The final score is `0.5 × deterministic + 0.5 × LLM`. Each stage sees something the
other cannot:

- the **engine** knows exact skill-set membership and precise seniority bands — facts,
  not judgements
- the **LLM** understands language the taxonomy has never been taught

Keeping both also bounds the damage: a wild LLM score can only move a result so far.
The API returns `engine_score` and `llm_relevance` separately alongside the blended
`score`, so the contribution of each stage is always visible rather than inferred.

#### Why not LLM-only

Three reasons, and they are the same reasons stage 1 exists at all:

1. **It cannot fail during a live demo.** The deterministic path needs no key, no
   network and no third party's uptime.
2. **Every stage-1 number is explainable.** I can point at the exact IDF term that
   produced a score.
3. **It is reproducible, so it is testable.** The ranking guarantees in the test suite
   are only possible because stage 1 is deterministic.

Sending 8 candidates instead of the whole corpus also keeps the prompt small, the
latency near 2–3 seconds, and the cost at zero on Groq's free tier.

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
| `POST` | `/match` | Optional | Rank open jobs against a natural-language query. Body: `query`, `limit`, `use_profile`, `use_llm`. Returns `llm_used` / `llm_model` / `llm_available` so callers know which path ran |
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
│   │   │   ├── engine.py       stage 1: 7-signal scoring + explanations
│   │   │   └── llm.py          stage 2: optional LLM re-rank (fails safe)
│   │   └── routers/
│   │       ├── auth.py  jobs.py  candidates.py
│   │       ├── applications.py  matching.py  dashboard.py
│   └── tests/
│       ├── test_matching.py    17 engine tests
│       └── test_api.py          8 API tests (closed-job + LLM fallback)
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

**25 tests, all passing**, in two files.

`test_matching.py` — **17 tests** on the scoring engine in isolation, no database. This is
where the real logic lives; each test states a behaviour worth defending:

- the brief's example query decomposes into all four signals
- aliases resolve (`js` → JavaScript, `healthtech` → Healthcare, `wfh` → remote)
- `react native` does not also register as `React`
- multi-word tokens (`node.js`, `ci/cd`, `c#`) survive tokenisation
- an unrecognised query returns an empty intent rather than guessing
- **domain and company stage outrank an identical job title**
- **role type outranks domain alone**
- signals the query never mentioned do not penalise a job
- every result carries a non-empty explanation

`test_api.py` — **8 tests** on behaviour that only exists once HTTP, auth and the database
are involved, each against a fresh in-memory database:

- **a closed listing never reaches the matcher** — the test *creates* a closed job and
  proves it is skipped while the open one is still returned (see the note below)
- a closed listing cannot be applied to
- **matching works with no API key** — full deterministic response, `llm_used: false`
- **a broken API key degrades instead of 500-ing** — `llm_available: true`, `llm_used: false`
- `use_llm: false` skips the LLM entirely
- role and ownership guards; duplicate applications rejected with 409

> **Why the closed-job test is written the way it is.** My first version of this check
> asserted "no closed job appeared in the results" — which passes trivially when the
> database happens to contain no closed jobs. It did exactly that, and I only noticed when
> a stale demo database made a *correct* implementation look broken. The test now creates
> the closed listing itself, so it can only pass for the right reason.

The full feature set is additionally verified end-to-end against the running API —
55 checks covering auth and role guards, job CRUD and ownership, search and filtering,
profiles, the AI matcher, the application pipeline, dashboard aggregates and error codes.

The full feature set was additionally verified end-to-end against the running API —
55 checks covering auth and role guards, job CRUD and ownership, search and filtering,
profiles, the AI matcher, the application pipeline, dashboard aggregates and error codes.

---

## Known limitations and what I would do next

**Where the matcher is weakest.** Stage 1's parser only understands vocabulary in
`taxonomy.py`, and it is English-only and India-centric on locations. Stage 2 covers that
gap when a key is configured — but with no key, novel phrasing falls through to TF-IDF
alone and precision drops (measurably: 25.3% vs 60.1% on the example above).

**Where the LLM layer is weakest.** Groq's free tier is rate-limited (~30 req/min), which
is fine for a demo and not for production. LLM scores are also not reproducible run to run,
which is exactly why the ranking guarantees in the test suite assert against stage 1 only.

**What I would build next, in priority order:**

1. **Sentence embeddings as an eighth stage-1 signal.** Encode the query and each job with a
   sentence-transformer and cache the job vectors. This closes the vocabulary gap *inside*
   the deterministic path, so it works offline too rather than depending on stage 2.
2. **Cache LLM verdicts** keyed by `(query, job set)`. Repeated demo queries currently pay
   the full round trip every time.
3. **Learn the weights instead of hand-tuning them.** The seven stage-1 weights and the
   50/50 blend are currently my judgement. With real application data, logistic regression
   on "did this candidate apply?" would replace guesses with evidence.
4. **Normalise skills into their own table** so they can be indexed, deduplicated globally, and
   filtered in SQL rather than in Python.
5. **Alembic migrations**, PostgreSQL, refresh tokens and rate limiting before any real deployment.
6. **Frontend tests.** The backend has 25; the React layer currently has none.

**Smaller known gaps:** no pagination UI (the API supports `limit`/`offset`); no email
notifications on status change; no resume/file upload; no full-text search index, so keyword
search is a `LIKE` scan that would need Postgres full-text or Elasticsearch at scale.
