from datetime import datetime, timezone
from typing import Any, Optional

from sqlalchemy import (
    BigInteger,
    DateTime,
    Index,
    Integer,
    Numeric,
    String,
    Text,
    UniqueConstraint,
    func,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


class Job(Base):
    """Bảng lưu trữ tin tuyển dụng IT từ các nền tảng (VietnamWorks, TopDev, TopCV, ITviec)."""

    __tablename__ = "jobs"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    source: Mapped[str] = mapped_column(String(50), nullable=False, index=True)
    external_id: Mapped[Optional[str]] = mapped_column(String(100), nullable=True, index=True)

    title: Mapped[str] = mapped_column(Text, nullable=False)
    company_name: Mapped[Optional[str]] = mapped_column(Text, nullable=True, index=True)
    company_logo: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    location: Mapped[Optional[str]] = mapped_column(Text, nullable=True, index=True)
    salary_min: Mapped[Optional[float]] = mapped_column(Numeric(15, 2), nullable=True)
    salary_max: Mapped[Optional[float]] = mapped_column(Numeric(15, 2), nullable=True)
    currency: Mapped[str] = mapped_column(String(10), nullable=False, default="VND")
    salary_text: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    job_url: Mapped[str] = mapped_column(Text, nullable=False, unique=True)
    description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    requirements: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    benefits: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    skills: Mapped[list[str]] = mapped_column(JSONB, nullable=False, default=list)
    job_level: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    working_type: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    posted_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    expired_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)

    raw_data: Mapped[Optional[dict[str, Any]]] = mapped_column(JSONB, nullable=True)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=utc_now,
        nullable=False,
    )

    __table_args__ = (
        UniqueConstraint("job_url", name="uq_jobs_job_url"),
        Index("ix_jobs_source_posted_at", "source", "posted_at"),
    )


class CrawlRun(Base):
    """Bảng lưu lịch sử các lần chạy crawler hàng ngày."""

    __tablename__ = "crawl_runs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    source: Mapped[str] = mapped_column(String(50), nullable=False, index=True)
    status: Mapped[str] = mapped_column(String(30), nullable=False, default="RUNNING")
    total_fetched: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    inserted_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    updated_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    error_message: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    started_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utc_now, nullable=False
    )
    finished_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), nullable=True
    )

