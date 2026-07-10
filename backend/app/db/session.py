from sqlmodel import Session, SQLModel, create_engine

from backend.app.core.config import settings


engine = create_engine(
    settings.database_url_sync,
    pool_pre_ping=True,
    pool_size=10,
    max_overflow=5,
    pool_recycle=3600,
    echo=settings.debug,
)


def init_db() -> None:
    from backend.app import models  # noqa: F401

    SQLModel.metadata.create_all(engine)


def get_session():
    with Session(engine) as session:
        yield session
