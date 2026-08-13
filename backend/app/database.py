"""Database engine, session factory and the FastAPI session dependency."""

from collections.abc import Generator

from sqlalchemy import create_engine
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker

from app.config import settings

# `check_same_thread=False` is required because FastAPI serves requests from a
# thread pool while SQLite defaults to one-thread-per-connection.
connect_args = {"check_same_thread": False} if settings.database_url.startswith("sqlite") else {}

engine = create_engine(settings.database_url, connect_args=connect_args)
SessionLocal = sessionmaker(bind=engine, autocommit=False, autoflush=False)


class Base(DeclarativeBase):
    """Declarative base every ORM model inherits from."""


def get_db() -> Generator[Session, None, None]:
    """Yield a request-scoped session and always close it afterwards."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
