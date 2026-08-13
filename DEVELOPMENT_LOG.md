# Development Log

How this project was built, phase by phase — the decisions taken at each step, the
reasoning behind them, and the problems found and fixed along the way.

This document exists so that during the live demo I can talk through *why* the system
looks the way it does, not just *what* it does.

---

## Contents

- [Phase 0 — Reading the brief and setting up](#phase-0--reading-the-brief-and-setting-up)
- [Phase 1 — Backend foundation and data model](#phase-1--backend-foundation-and-data-model)
- [Phase 2 — Authentication and role guards](#phase-2--authentication-and-role-guards)
- [Phase 3 — Job listings, search and filtering](#phase-3--job-listings-search-and-filtering)
- [Phase 4 — Candidate profiles and the application pipeline](#phase-4--candidate-profiles-and-the-application-pipeline)
- [Phase 5 — The AI matching engine](#phase-5--the-ai-matching-engine)
- [Phase 6 — Admin dashboard](#phase-6--admin-dashboard)
- [Phase 7 — React frontend](#phase-7--react-frontend)
- [Phase 8 — End-to-end verification](#phase-8--end-to-end-verification)
- [Phase 9 — Documentation and submission](#phase-9--documentation-and-submission)
- [Problems hit and how they were solved](#problems-hit-and-how-they-were-solved)
- [Demo script](#demo-script)

---

## Phase 0 — Reading the brief and setting up

**Goal:** turn the assignment into a build order, and decide the two things that would
constrain everything else.

I pulled the required features out of the brief and grouped them:

| Requirement from the brief | Where it landed |
|---|---|
| Admin: create/edit/manage listings (title, description, skills, experience, location, status) | Phase 3 |
| Candidate: profile with name, skills, education, projects, preferences | Phase 4 |
| AI matching from natural language, ranked, with an explanation each | Phase 5 |
| Apply to a job, application includes profile details | Phase 4 |
| Admin views applications per job, status Applied → Shortlisted → Rejected | Phase 4 |
| Dashboard: applications per job, skill distribution, pipeline counts | Phase 6 |
| Search and filter by skills, location, experience level | Phase 3 |
| Python backend (Flask or FastAPI), REST, proper status codes and error handling | Phases 1–6 |
| React frontend, separate Admin and Candidate views, clean and functional | Phase 7 |

**Two decisions taken before writing any code.**

**1. The AI engine would be deterministic and dependency-free.** The brief requires a
*live* 30-minute demo with the system already running. An LLM-backed matcher introduces
an API key, a network dependency, latency, and a rate limit — four ways for the
centrepiece feature to fail in front of the panel. I chose an engine that cannot fail
that way, and wrote down the trade-off honestly in the README rather than hiding it.

**2. Build order: backend first, frontend last.** The API is the part the brief grades
explicitly ("RESTful endpoints with proper status codes and error handling"). Building it
first meant that by the time I wrote React, I was consuming an API I had already proven
worked.

**Setup:** `.gitignore` written before the first file, so `__pycache__`, `.venv`,
`node_modules`, `dist` and the SQLite database never entered git history.

---

## Phase 1 — Backend foundation and data model

**Files:** `config.py`, `database.py`, `models.py`

**Configuration with working defaults.** Every setting has a default, so the app boots
with zero configuration. A grader who clones the repo and forgets to copy `.env.example`
still gets a running server rather than a stack trace.

**SQLite with `check_same_thread=False`** — required because FastAPI serves requests from
a thread pool while SQLite defaults to one thread per connection.

**Four tables:** `users`, `candidate_profiles`, `jobs`, `applications`.

### Design decisions in the data model

**Extra job fields beyond the brief's minimum.** The brief's own example query is
*"a Python backend role in a startup that does healthcare"*. That sentence names a
**domain** and a **company stage**. If jobs only had the six fields the brief lists, the
matcher would have to guess both by scraping the description — unreliable, and impossible
to explain cleanly.

So `jobs` also has `domain`, `company_stage`, `work_mode`, `company_name` and
`min_years_experience`. Every one of them is optional, and every one feeds a specific
scoring signal in Phase 5. This is the single decision that most improved match quality.

**`Application.profile_snapshot` — a frozen copy of the profile at apply time.** The brief
says an application "includes the candidate's profile details". Two readings: join to the
live profile, or snapshot it. I chose snapshot because:

- an admin reviewing a three-week-old application should see what was actually submitted,
  not whatever the candidate has edited since;
- the dashboard's "skill distribution across applicants" is a historical question, and
  should not change retroactively when someone updates their profile.

**JSON columns for list-shaped data** (skills, education, projects, domain interests).
Honest trade-off: it keeps the schema small and readable at this size, but it cannot be
indexed — which is exactly why skill filtering in Phase 3 happens in Python. The
production fix is a normalised `job_skills` table, and that is noted in the README.

**A unique constraint on `(job_id, candidate_id)`** so a candidate cannot apply twice —
enforced at the database level, not just in application code.

---

## Phase 2 — Authentication and role guards

**Files:** `security.py`, `deps.py`, `schemas.py`, `routers/auth.py`

**Password hashing: PBKDF2-HMAC-SHA256, 260,000 iterations, per-user random salt.**

I started to reach for `passlib[bcrypt]`, then chose the standard library instead.
`passlib` and `bcrypt` 4.x have a well-known version conflict that fails at import time,
and it fails most often on Windows — which is where this demo will run. PBKDF2 from
`hashlib` is a correct, salted, deliberately slow KDF with zero dependency risk.
Argon2id would be the production choice; I say so in the code comment.

Verification uses `hmac.compare_digest` — constant-time, so the comparison cannot leak
information through timing.

**JWT with PyJWT.** Stateless, carries `sub` (user id) and `role`, 12-hour expiry so a
demo session never expires mid-presentation.

**Four dependencies rather than one.** `get_current_user`, `get_current_admin`,
`get_current_candidate`, and `get_optional_user`. Splitting them means each endpoint
declares its own access requirement in its signature, and the OpenAPI docs reflect it
automatically. `get_optional_user` exists specifically for AI matching, which works
anonymously but gets better when signed in.

**Login does not distinguish "no such user" from "wrong password".** Same message, same
status code — otherwise the endpoint becomes a way to enumerate which emails are registered.

**Registration returns a token.** The UI signs the user straight in rather than bouncing
them to a second login screen.

**Registration creates an empty candidate profile immediately**, so the frontend never
has to handle a "profile does not exist yet" branch.

---

## Phase 3 — Job listings, search and filtering

**File:** `routers/jobs.py`

**Reads are public, writes require an admin.** A candidate browses before signing in.

**Ownership checks, not just role checks.** `_get_own_job` asserts
`job.created_by == admin.id` before any update or delete. Being an admin is not enough to
edit someone else's listing — two companies can use the same instance safely. This is
verified in the E2E suite (admin B gets `403` editing admin A's job).

**Skill filtering happens in Python, not SQL.** `required_skills` is a JSON column and
SQLite cannot index inside it. At this dataset size the cost is negligible. I wrote the
reason in a comment rather than leaving it looking like an oversight, and named the fix
(a normalised join table).

**A separate `PATCH /jobs/{id}/status` endpoint** so the UI can open/close a listing in
one click without sending the whole job body back.

---

## Phase 4 — Candidate profiles and the application pipeline

**Files:** `routers/candidates.py`, `routers/applications.py`

**Profile uses `PUT`, not `PATCH`** — the body is the complete profile, so sending it
twice produces the same result. Idempotent by design.

**Applying is guarded three ways:** the job must exist (`404`), it must be open (`400`),
and the candidate must not have applied already (`409`). There is also a fourth check —
the candidate must have at least skills on their profile (`400`) — because an application
with an empty snapshot is useless to the admin reviewing it.

**Pipeline transitions are unrestricted between the three states.** An admin can move
someone back to Applied or un-reject them. Real hiring is not a one-way funnel. The
*values* are constrained to exactly three by a Pydantic enum, so anything else is a `422`
before it reaches the handler.

**Candidates can withdraw their own applications**, and only their own.

---

## Phase 5 — The AI matching engine

The core of the assignment. Built as five small modules rather than one file, so each
piece can be explained and tested independently.

### `taxonomy.py` — vocabulary as data, not logic

~70 canonical skills, 17 domains, 13 role types, 10 locations, plus work modes, company
stages and seniority levels — each mapped to the surface forms people actually type
(`js`, `k8s`, `healthtech`, `wfh`, `sr.`).

Keeping this as pure data means adding a skill is a one-line change and the matcher's
entire vocabulary is auditable at a glance.

**Aliases are sorted longest-first** so multi-word forms win over their own substrings.

### `text.py` — tokenisation

Dependency-free on purpose: no NLTK, no spaCy, no model download that could fail on a
fresh machine.

The token pattern keeps `+ # . / -` **inside** words. Without that, `c++` becomes `c`,
`node.js` becomes `node` + `js`, and `ci/cd` becomes two meaningless letters. There is a
test pinning this.

Bigrams are included as features so `machine learning` is one signal rather than two
unrelated words.

### `tfidf.py` — TF-IDF from scratch

~60 lines. I chose not to use scikit-learn, and the reasoning is in the module docstring:

1. It is 60 lines of arithmetic — pulling in a 30 MB dependency (plus a pinned
   NumPy/SciPy build that breaks on some Windows setups) is a bad trade.
2. **I can explain every number the matcher produces.** In an interview about an AI
   feature, "sklearn returned 0.62" is a worse answer than pointing at the exact IDF
   term that caused it.
3. The corpus is tens of documents. At millions I would use a vector database and
   precomputed embeddings instead — and I say so.

`top_overlapping_terms()` exists purely for explainability: it reports which terms
contributed most to a similarity score, so the UI can say *why* rather than just showing
a number.

### `parser.py` — natural language to structured intent

Alias matching plus a regex for numeric years. Once an alias matches, that span is blanked
out of the working copy so a shorter alias cannot fire on the same text.

`enrich_with_profile()` folds a candidate's saved profile into the intent, but **the query
always wins** — profile values only fill gaps the query left empty. Typing "I want a
frontend role" while having a backend-heavy profile still returns frontend jobs.

`is_empty()` lets the system report honestly when it understood nothing structured, rather
than pretending confidence it does not have.

### `engine.py` — the weighted ensemble

Seven signals, each 0–1, combined as a weighted mean.

**The key design decision: inactive signals are switched off and their weight
redistributed.** If the query never mentions a domain, the domain signal does not score 0
— it is excluded and the remaining weights are renormalised. Without this, asking
"remote Python job" would silently penalise every listing for not matching a domain the
candidate never named.

**Semantic calibration.** Raw cosine between a one-sentence query and a full job
description rarely exceeds ~0.45 even for an ideal match, because the description carries
far more vocabulary. Dividing by that constant maps a realistic best case onto 1.0
instead of leaving every score bunched at the bottom of the range. The constant is
documented as empirical, not derived.

**Skills scoring blends two views:** recall (of the skills asked for, how many does this
job want?) weighted 0.70, and coverage (of the skills this job requires, how many does the
candidate have?) weighted 0.30. Recall dominates because the candidate's stated intent is
what is being served; coverage stops a job requiring 15 skills from scoring as highly as
one requiring exactly the 3 named.

**Explanations are generated from the numeric breakdown**, so they can never disagree with
the score.

### A bug found by testing the output, not the code

After the first working version I ran the brief's example query and read the ranking:

```
[69.1%] Python Backend Engineer            Healthcare/startup
[64.5%] Senior Backend Engineer            Healthcare/startup
[60.8%] QA Automation Engineer             Healthcare/startup   ← wrong
[58.3%] Machine Learning Engineer          Healthcare/startup   ← wrong
[42.8%] Python Backend Engineer, Payments  Fintech/midsize
```

The top result was right, but a QA role and an ML role were outranking nothing in
particular — and the parser had clearly extracted `role_types: ["Backend"]`.

**The parser was extracting role type and the engine was never scoring it.** The signal
was parsed, displayed in the API response, and then silently dropped.

Fix: added a seventh signal with weight 0.15, inferring each job's discipline from its
title (falling back to the description), with an adjacency map so Full Stack is a partial
match for Backend rather than a total miss. Rebalanced the other weights to compensate.

Result:

```
[75.2%] Python Backend Engineer            Healthcare/startup
[71.5%] Senior Backend Engineer            Healthcare/startup
[51.9%] Python Backend Engineer, Payments  Fintech/midsize
[51.4%] QA Automation Engineer             Healthcare/startup
[49.4%] Machine Learning Engineer          Healthcare/startup
```

Two tests were added to stop it regressing: `test_role_type_outranks_domain_alone` and
`test_domain_and_stage_outrank_an_identical_title`.

**The lesson worth stating in the demo:** the bug was invisible in the code and obvious in
the output. Nothing threw an exception; a field was simply parsed and never used. I found
it by reading results against expectations rather than by re-reading the implementation.

### Seed data designed to make the matcher prove itself

The dataset is deliberately adversarial. It contains **two listings with the same title
and the same required skills**, differing only in domain and company stage — so the brief's
example query cannot be answered correctly by keyword matching. It also includes a closed
listing, so the "only open jobs are matched" rule is demonstrable rather than asserted.

### 17 tests

They target the matcher because that is the part with real logic. Each test states a
behaviour I would defend out loud, not a value that happens to be true today — including
the `react native` / `React` alias-collision case, multi-word token survival, and the two
ranking guarantees above.

---

## Phase 6 — Admin dashboard

**File:** `routers/dashboard.py`

All three aggregates the brief asks for, scoped to the calling admin's own listings.

**Skill distribution is computed from `profile_snapshot`, not the live profile.** "What
skills did our applicants have?" is a historical question. Reading the snapshot means the
answer does not change when a candidate edits their profile next week.

Each skill is counted **once per application**, not once per mention, so the numbers mean
"how many applicants have this skill".

The E2E suite checks that per-job totals reconcile with the grand total — a cheap
invariant that would catch a bad `GROUP BY` immediately.

---

## Phase 7 — React frontend

**Structure:** one API client, one auth context, a role-gated router, and pages that
never think about permissions.

**`api.js` — every call goes through one `request()` function.** Token attachment and
error unwrapping live in exactly one place. Because the backend always returns
`{"detail": "..."}`, the UI can render `err.message` directly with no per-endpoint
error handling.

**`auth.jsx` — the token is re-validated on mount.** Rather than trusting a cached user
object from localStorage, the app calls `/auth/me` on load. An expired or revoked token
is caught immediately instead of failing on the first real request.

**Role gating in the router, not in components.** `App.jsx` renders one of two route sets.
A page can assume it would not have rendered if the user were not allowed. The backend
enforces the same rules independently — the frontend layer is UX, not security.

**The AI Match page is built to be inspectable.** It shows:

- **what the parser understood**, as chips — so when the matcher gets something wrong, the
  panel can see *where* it went wrong;
- the **score**, colour-coded by band;
- the **explanation** and bullet-point reasons;
- the **full seven-signal breakdown** as bars;
- matched skills highlighted green, gap skills listed.

That last piece matters for the demo: an AI feature that shows only a number invites
"how do you know it works?". Showing the breakdown answers it before it is asked.

**Five preset example queries**, including the brief's own, so the demo does not depend on
me typing accurately under pressure.

**Hand-written CSS**, ~400 lines. A component library would be a dependency I would have
to justify; this I can explain.

---

## Phase 8 — End-to-end verification

Two layers.

**Unit tests:** `pytest tests -q` → **17 passed**.

**End-to-end against the live API: 55 checks, all passing.** Written as a throwaway script
that walks the brief requirement by requirement:

| Group | Checks | Covers |
|---|---|---|
| Auth and roles | 6 | JWT issue, wrong password `401`, missing token `401`, wrong role `403` |
| Admin job management | 6 | create `201`, edit, status toggle, candidate blocked `403`, cross-admin blocked `403` |
| Search and filtering | 5 | by skill, location, experience level, keyword, combined |
| Candidate profile | 4 | all brief fields present, education, projects, update |
| **AI matching** | **14** | parse correctness, ranking order, top result correct, fintech demoted, closed jobs excluded, explanations present, profile blending |
| Applications and pipeline | 11 | apply `201`, snapshot, duplicate `409`, all three transitions, invalid status `422`, cross-admin `403` |
| Dashboard | 5 | all three aggregates, totals reconcile |
| Error handling | 4 | `404`, `422`, `409`, consistent `{detail}` shape |

**Frontend:** production build succeeds (49 modules), and all 17 source modules compile
and serve cleanly through Vite.

---

## Phase 9 — Documentation and submission

`README.md` covers everything the submission checklist asks for — tech stack, architecture
decisions, setup instructions and assumptions — plus an API reference, the matching
algorithm explained with its formulae, and an honest limitations section.

This log covers the build narrative and the reasoning.

**Only source files are committed.** `.gitignore` keeps `.venv/`, `node_modules/`,
`dist/`, `__pycache__/`, `.env` and the SQLite database out of the repository.

---

## Problems hit and how they were solved

| # | Problem | Root cause | Fix |
|---|---|---|---|
| 1 | `passlib[bcrypt]` risked failing at import on Windows | Known bcrypt 4.x incompatibility | Used `hashlib.pbkdf2_hmac` from the standard library — no dependency, still correctly salted and slow |
| 2 | Role type was parsed and displayed but never scored, so a QA role outranked backend roles | Signal existed in the parser and the response schema but had no branch in the engine | Added a seventh signal (weight 0.15) with title-based inference and an adjacency map; rebalanced weights; added two regression tests |
| 3 | Raw cosine scores were all bunched near the bottom of the range | A one-sentence query shares little vocabulary with a full job description | Divide by an empirical calibration constant (0.45) so a realistic best case maps to 1.0 — documented as empirical, not derived |
| 4 | Queries mentioning only skills scored every job poorly | Unmentioned signals were contributing 0 to a fixed-weight average | Made signals activate/deactivate, and renormalise weights across active signals only |
| 5 | `react native` also matched the bare `react` alias, inflating scores | Alias list was unordered | Sort aliases longest-first and blank out matched spans; pinned with a test |
| 6 | Skill filter could not be expressed in SQL | `required_skills` is a JSON column, unindexable in SQLite | Filter in Python, document the reason in a comment, and name the production fix (normalised join table) |
| 7 | The first code change did not take effect | `uvicorn` was started without `--reload` | Restarted with `--reload`; noted for the demo runbook |
| 8 | Vite reported "ready" but connections were refused | Vite binds `localhost` (IPv6 `::1` on Windows); tests were hitting `127.0.0.1` | Use `http://localhost:5173`; also cleaned up an orphaned node process holding the port |

---

## Demo script

A 30-minute run through that hits every graded feature.

**Before the call:** both servers running, `python -m app.seed --reset` already executed,
browser open at `http://localhost:5173`, and a second tab on `http://127.0.0.1:8000/docs`.

**1. Architecture (3 min)** — slides: the two roles, the request path, and the five
matching modules.

**2. Company Admin (7 min)** — sign in as `admin@medicore.io`.
- Dashboard: applications per job, skill distribution, pipeline counts.
- My Job Listings → Post a Job. Point out `domain` and `company_stage`, and say why they
  exist: *the brief's example query names both.*
- Open a job's applicants → move one Applied → Shortlisted → return to the dashboard and
  show the count moved.
- Expand "View full profile" and note it is a snapshot, not the live profile — and why.

**3. Candidate (5 min)** — sign in as `sana.k@example.com`.
- Profile: skills, education, projects, preferences.
- Browse Jobs: filter by skill, then location, then experience level.

**4. AI matching (10 min — the centrepiece)**
- Paste the brief's own query: *"I want a Python backend role in a startup that does healthcare."*
- Show **what the system understood** — the parsed chips. Emphasise that this is
  inspectable, not a black box.
- Walk the top result: score, explanation, reasons, seven-signal breakdown.
- **The proof it is not keyword search:** scroll to *Python Backend Engineer, Payments* at
  FinStack — identical title, identical skills, 23 points lower, because the domain and
  stage are wrong. Then note the QA role at MediCore, which has the right domain and stage
  but the wrong discipline, and also ranks below.
- Run a second query — *"remote React and TypeScript work at a fintech company"* — to show
  the ranking genuinely changes.
- Untick "blend in my saved profile" and re-run to show the profile's contribution.

**5. Engineering (5 min)**
- `pytest tests -q` → 17 passing; open `test_matching.py` and read the two ranking tests.
- `/docs` → show status codes and the consistent `{"detail": ...}` error shape.
- Walk `engine.py`'s weight table and explain the active-signal renormalisation.

**6. What I would improve (2 min)** — the limitations section of the README, in priority
order: sentence embeddings as an eighth signal, an LLM re-ranker behind a feature flag
with fallback to the deterministic path, and learning the weights from real application
data instead of hand-tuning them.

### Questions to be ready for

| Likely question | Short answer |
|---|---|
| "Why is this AI if there's no LLM?" | It is an information-retrieval system: TF-IDF vectorisation, cosine similarity, and a weighted ensemble over structured intent. I chose determinism over an LLM for demo reliability and explainability, and the README states exactly how I would add an LLM layer without losing either. |
| "How did you pick the weights?" | Hand-tuned against the seed corpus and sanity-checked by reading rankings. That is a real limitation — with application data I would fit them with logistic regression on "did this candidate apply?". |
| "Why 0.45 for semantic calibration?" | Empirical. A one-sentence query shares little vocabulary with a full description, so raw cosine tops out around 0.45 for an ideal match. It is a documented constant, not a derived one. |
| "What happens with a query you've never seen?" | The parser returns an empty intent and the system falls back to TF-IDF alone — and the UI says so explicitly rather than faking confidence. |
| "Where does this break at scale?" | The TF-IDF index rebuilds per request — fine for tens of jobs, wrong at 100k. Skills filtering in Python has the same ceiling. Both fixes are in the README. |
| "What would you do differently?" | Add the role-type signal from the start — I built the parser and the engine separately and let a parsed field go unused. A schema-level check that every parsed signal has a consumer would have caught it on day one. |
