from contextlib import contextmanager
from sqlalchemy import create_engine
from sqlalchemy.orm import DeclarativeBase, sessionmaker

from app.config import settings


class Base(DeclarativeBase):
    pass


engine = create_engine(
    settings.database_url,
    pool_pre_ping=True,
    pool_size=5,
    max_overflow=10,
)

SessionLocal = sessionmaker(
    autocommit=False, autoflush=False, expire_on_commit=False, bind=engine
)


def init_db() -> None:
    """Tạo bảng trong PostgreSQL nếu chưa tồn tại và tạo các view phân tích."""
    import app.models  # noqa: F401
    from pathlib import Path
    from sqlalchemy import text

    Base.metadata.create_all(bind=engine)

    sql_file = Path(__file__).resolve().parent.parent / "init_views.sql"
    if sql_file.exists():
        try:
            sql_content = sql_file.read_text(encoding="utf-8")
            with engine.begin() as conn:
                conn.execute(text(sql_content))
        except Exception:
            pass


@contextmanager
def get_db_session():
    session = SessionLocal()
    try:
        yield session
        session.commit()
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()
