from sqlmodel import Session, SQLModel, create_engine

from backend.app.core.config import settings


engine_kwargs = {"pool_pre_ping": True}
if settings.database_url_sync.startswith("sqlite"):
    engine_kwargs["connect_args"] = {"check_same_thread": False}

engine = create_engine(settings.database_url_sync, **engine_kwargs)


def init_db() -> None:
    from backend.app import models  # noqa: F401

    SQLModel.metadata.create_all(engine)


def get_session():
    with Session(engine) as session:
        yield session
