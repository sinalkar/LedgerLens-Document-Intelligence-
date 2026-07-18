from collections.abc import Iterator

from sqlalchemy import create_engine
from sqlalchemy.engine import Engine
from sqlalchemy.orm import Session, sessionmaker

from app.config import get_settings
from app.storage.models import Base

# Engines cached per URL so tests (which point DATABASE_URL at temp files)
# and the app never share stale connections.
_engines: dict[str, Engine] = {}


def get_engine() -> Engine:
    url = get_settings().database_url
    engine = _engines.get(url)
    if engine is None:
        kwargs = {}
        if url.startswith("sqlite"):
            kwargs["connect_args"] = {"check_same_thread": False}
        engine = create_engine(url, **kwargs)
        _engines[url] = engine
    return engine


def init_db() -> None:
    Base.metadata.create_all(get_engine())


def get_db() -> Iterator[Session]:
    SessionLocal = sessionmaker(
        bind=get_engine(), autoflush=False, expire_on_commit=False
    )
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
