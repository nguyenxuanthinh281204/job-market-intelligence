from datetime import datetime, timezone
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.orm import Session

from app.models import CrawlRun, Job


def upsert_jobs(session: Session, jobs_data: list[dict[str, Any]]) -> tuple[int, int]:
    """
    Thực hiện Upsert (Insert hoặc Update nếu trùng job_url) vào PostgreSQL.
    Trả về (inserted_count, updated_count).
    """
    if not jobs_data:
        return 0, 0

    # Khử trùng lặp theo job_url ngay trong batch trước khi gửi tới PostgreSQL
    deduped_map: dict[str, dict[str, Any]] = {}
    for item in jobs_data:
        url = (item.get("job_url") or "").strip()
        if url:
            deduped_map[url] = item

    unique_jobs = list(deduped_map.values())
    if not unique_jobs:
        return 0, 0

    urls = [j["job_url"] for j in unique_jobs]
    existing_urls = set(
        session.scalars(select(Job.job_url).where(Job.job_url.in_(urls))).all()
    )

    now = datetime.now(timezone.utc)
    batch_size = 150

    for i in range(0, len(unique_jobs), batch_size):
        batch = unique_jobs[i : i + batch_size]
        stmt = insert(Job).values(batch)
        update_cols = {
            "external_id": stmt.excluded.external_id,
            "title": stmt.excluded.title,
            "company_name": stmt.excluded.company_name,
            "company_logo": stmt.excluded.company_logo,
            "location": stmt.excluded.location,
            "salary_min": stmt.excluded.salary_min,
            "salary_max": stmt.excluded.salary_max,
            "currency": stmt.excluded.currency,
            "salary_text": stmt.excluded.salary_text,
            "description": stmt.excluded.description,
            "requirements": stmt.excluded.requirements,
            "benefits": stmt.excluded.benefits,
            "skills": stmt.excluded.skills,
            "job_level": stmt.excluded.job_level,
            "working_type": stmt.excluded.working_type,
            "posted_at": stmt.excluded.posted_at,
            "expired_at": stmt.excluded.expired_at,
            "raw_data": stmt.excluded.raw_data,
            "updated_at": now,
        }
        upsert_stmt = stmt.on_conflict_do_update(
            index_elements=[Job.job_url],
            set_=update_cols,
        )
        session.execute(upsert_stmt)

    updated_count = len(existing_urls)
    inserted_count = len(unique_jobs) - updated_count
    return inserted_count, updated_count


def create_crawl_run(session: Session, source: str) -> CrawlRun:
    run = CrawlRun(
        source=source,
        status="RUNNING",
        started_at=datetime.now(timezone.utc),
    )
    session.add(run)
    session.flush()
    return run


def finish_crawl_run(
    session: Session,
    run: CrawlRun,
    *,
    status: str,
    total_fetched: int,
    inserted_count: int,
    updated_count: int,
    error_message: str | None = None,
) -> None:
    run.status = status
    run.total_fetched = total_fetched
    run.inserted_count = inserted_count
    run.updated_count = updated_count
    run.error_message = error_message
    run.finished_at = datetime.now(timezone.utc)
    session.add(run)


def get_database_stats(session: Session) -> dict[str, Any]:
    total_jobs = session.scalar(select(func.count(Job.id))) or 0
    by_source = session.execute(
        select(Job.source, func.count(Job.id)).group_by(Job.source)
    ).all()
    recent_runs = session.scalars(
        select(CrawlRun).order_by(CrawlRun.started_at.desc()).limit(10)
    ).all()
    return {
        "total_jobs": total_jobs,
        "by_source": {row[0]: row[1] for row in by_source},
        "recent_runs": recent_runs,
    }


def export_jobs_to_file(
    session: Session,
    output_path: str,
    export_format: str = "csv",
    source: str | None = None,
) -> int:
    """Xuất danh sách công việc trong DB ra file CSV hoặc JSON."""
    import csv
    import json

    query = select(Job).order_by(Job.id.desc())
    if source:
        query = query.where(Job.source == source)

    jobs = session.scalars(query).all()
    if not jobs:
        return 0

    if export_format.lower() == "json":
        data = [
            {
                "id": j.id,
                "source": j.source,
                "external_id": j.external_id,
                "title": j.title,
                "company_name": j.company_name,
                "location": j.location,
                "salary_min": float(j.salary_min) if j.salary_min is not None else None,
                "salary_max": float(j.salary_max) if j.salary_max is not None else None,
                "currency": j.currency,
                "salary_text": j.salary_text,
                "job_url": j.job_url,
                "skills": j.skills,
                "job_level": j.job_level,
                "working_type": j.working_type,
                "posted_at": j.posted_at.isoformat() if j.posted_at else None,
            }
            for j in jobs
        ]
        with open(output_path, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
    else:
        fieldnames = [
            "id",
            "source",
            "title",
            "company_name",
            "location",
            "salary_min",
            "salary_max",
            "currency",
            "salary_text",
            "skills",
            "job_level",
            "job_url",
            "posted_at",
        ]
        with open(output_path, "w", encoding="utf-8-sig", newline="") as f:
            writer = csv.DictWriter(f, fieldnames=fieldnames)
            writer.writeheader()
            for j in jobs:
                writer.writerow(
                    {
                        "id": j.id,
                        "source": j.source,
                        "title": j.title,
                        "company_name": j.company_name or "",
                        "location": j.location or "",
                        "salary_min": j.salary_min if j.salary_min is not None else "",
                        "salary_max": j.salary_max if j.salary_max is not None else "",
                        "currency": j.currency,
                        "salary_text": j.salary_text or "",
                        "skills": ", ".join(j.skills) if isinstance(j.skills, list) else "",
                        "job_level": j.job_level or "",
                        "job_url": j.job_url,
                        "posted_at": j.posted_at.isoformat() if j.posted_at else "",
                    }
                )

    return len(jobs)


