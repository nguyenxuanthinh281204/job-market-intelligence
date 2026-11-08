from contextlib import asynccontextmanager
from typing import Any, Optional

from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.cron import CronTrigger
from fastapi import BackgroundTasks, FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field
from sqlalchemy import func, select

from app.config import settings
from app.database import get_db_session, init_db
from app.models import CrawlRun, Job
from app.pipeline import run_daily_crawl
from app.repository import get_database_stats, upsert_jobs


scheduler = BackgroundScheduler(timezone=settings.timezone)


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Khởi tạo DB khi API server bật
    init_db()

    # Khởi động Cron Scheduler chạy ngầm song song với API server
    trigger = CronTrigger(
        hour=settings.crawl_cron_hour,
        minute=settings.crawl_cron_minute,
        timezone=settings.timezone,
    )
    scheduler.add_job(
        run_daily_crawl,
        trigger=trigger,
        id="daily_it_job_crawl_api",
        name="Thu thập dữ liệu việc làm IT hàng ngày",
        replace_existing=True,
        max_instances=1,
        coalesce=True,
    )
    scheduler.start()

    yield

    if scheduler.running:
        scheduler.shutdown(wait=False)


app = FastAPI(
    title="IT Job Market Intelligence API",
    description="Hệ thống API thu thập, lưu trữ và phân tích dữ liệu tuyển dụng IT.",
    version="1.0.0",
    lifespan=lifespan,
)

# Cho phép Chrome Extension và các ứng dụng frontend gọi API
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


class JobItemInput(BaseModel):
    source: str = "TopCV"
    title: str
    company_name: Optional[str] = None
    company_logo: Optional[str] = None
    location: Optional[str] = None
    salary_min: Optional[float] = None
    salary_max: Optional[float] = None
    currency: str = "VND"
    salary_text: Optional[str] = None
    job_url: str
    description: Optional[str] = None
    requirements: Optional[str] = None
    benefits: Optional[str] = None
    skills: list[str] = Field(default_factory=list)
    job_level: Optional[str] = None
    working_type: Optional[str] = None


class BulkJobInput(BaseModel):
    jobs: list[JobItemInput]


@app.get("/")
def root():
    return {
        "status": "online",
        "service": "IT Job Market Intelligence API",
        "docs_url": "/docs",
    }


@app.post("/api/jobs/bulk")
def receive_jobs_from_extension(payload: BulkJobInput):
    """
    Endpoint nhận dữ liệu từ Chrome Extension (TopCV, ITviec, v.v.).
    Tương thích 100% với popup.js hiện có.
    """
    if not payload.jobs:
        return {"received": 0, "inserted": 0, "updated": 0}

    jobs_data = [j.model_dump() for j in payload.jobs]

    with get_db_session() as session:
        inserted, updated = upsert_jobs(session, jobs_data)

    return {
        "received": len(payload.jobs),
        "inserted": inserted,
        "updated": updated,
    }


@app.get("/api/jobs")
def get_jobs(
    keyword: Optional[str] = None,
    skill: Optional[str] = None,
    source: Optional[str] = None,
    limit: int = Query(default=20, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
):
    """Tìm kiếm và lọc danh sách việc làm IT trong database."""
    with get_db_session() as session:
        query = select(Job).order_by(Job.id.desc())

        if source:
            query = query.where(Job.source.ilike(f"%{source}%"))
        if keyword:
            query = query.where(Job.title.ilike(f"%{keyword}%"))
        if skill:
            query = query.where(Job.skills.contains([skill]))

        total = session.scalar(select(func.count()).select_from(query.subquery())) or 0
        items = session.scalars(query.offset(offset).limit(limit)).all()

        return {
            "total": total,
            "limit": limit,
            "offset": offset,
            "items": [
                {
                    "id": item.id,
                    "source": item.source,
                    "title": item.title,
                    "company_name": item.company_name,
                    "location": item.location,
                    "salary_min": float(item.salary_min) if item.salary_min is not None else None,
                    "salary_max": float(item.salary_max) if item.salary_max is not None else None,
                    "currency": item.currency,
                    "salary_text": item.salary_text,
                    "job_url": item.job_url,
                    "skills": item.skills,
                    "posted_at": item.posted_at.isoformat() if item.posted_at else None,
                }
                for item in items
            ],
        }


@app.get("/api/stats")
def get_stats():
    """Xem thống kê thị trường: tổng số job, phân bổ theo nguồn, lịch sử crawl."""
    with get_db_session() as session:
        stats = get_database_stats(session)
        return {
            "total_jobs": stats["total_jobs"],
            "by_source": stats["by_source"],
            "recent_runs": [
                {
                    "id": r.id,
                    "source": r.source,
                    "status": r.status,
                    "total_fetched": r.total_fetched,
                    "inserted_count": r.inserted_count,
                    "updated_count": r.updated_count,
                    "started_at": r.started_at.isoformat() if r.started_at else None,
                    "finished_at": r.finished_at.isoformat() if r.finished_at else None,
                }
                for r in stats["recent_runs"]
            ],
        }


@app.post("/api/crawl/trigger")
def trigger_crawl(background_tasks: BackgroundTasks, source: Optional[str] = None):
    """Kích hoạt chạy cào dữ liệu ngay lập tức dưới nền (asynchronous)."""
    background_tasks.add_task(run_daily_crawl, source_filter=source)
    return {"status": "accepted", "message": f"Đã bắt đầu chạy crawl nguồn: {source or 'Tất cả'}"}

