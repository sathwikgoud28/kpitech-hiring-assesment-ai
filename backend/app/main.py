"""FastAPI application entry point."""

from fastapi import FastAPI, Request, status
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from sqlalchemy.exc import IntegrityError

from app.config import settings
from app.database import Base, engine
from app.routers import applications, auth, candidates, dashboard, jobs, matching

# Import models so SQLAlchemy registers every table before create_all runs.
from app import models  # noqa: F401  (imported for the side effect)

app = FastAPI(
    title=settings.app_name,
    version="1.0.0",
    description=(
        "REST API for a job board with AI-powered candidate-to-job matching.\n\n"
        "Two roles: **Company Admin** (posts and manages listings, triages applicants) "
        "and **Candidate** (builds a profile, searches, applies, and uses natural-language "
        "matching)."
    ),
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origin_list,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.on_event("startup")
def on_startup() -> None:
    """Create tables on boot.

    Fine for a project of this size. A production deployment would use Alembic
    migrations instead, so schema changes are versioned and reversible.
    """
    Base.metadata.create_all(bind=engine)


# --------------------------------------------------------------------------- #
# Error handling - keep every error response the same shape: {"detail": "..."}
# --------------------------------------------------------------------------- #
@app.exception_handler(RequestValidationError)
async def validation_error_handler(_: Request, exc: RequestValidationError) -> JSONResponse:
    """Flatten Pydantic's nested error list into one readable sentence."""
    problems = []
    for error in exc.errors():
        location = " -> ".join(str(part) for part in error["loc"] if part != "body")
        problems.append(f"{location}: {error['msg']}" if location else error["msg"])
    return JSONResponse(
        status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
        content={"detail": "; ".join(problems) or "Invalid request payload."},
    )


@app.exception_handler(IntegrityError)
async def integrity_error_handler(_: Request, __: IntegrityError) -> JSONResponse:
    """A unique/foreign-key violation reaching this point means a race we lost."""
    return JSONResponse(
        status_code=status.HTTP_409_CONFLICT,
        content={"detail": "That record conflicts with one that already exists."},
    )


# --------------------------------------------------------------------------- #
# Routes
# --------------------------------------------------------------------------- #
app.include_router(auth.router)
app.include_router(jobs.router)
app.include_router(candidates.router)
app.include_router(applications.router)
app.include_router(matching.router)
app.include_router(dashboard.router)


@app.get("/api/health", tags=["meta"])
def health() -> dict:
    """Liveness probe - also a quick way to confirm the API is up before a demo."""
    return {"status": "ok", "service": settings.app_name}
