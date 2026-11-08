import logging
from typing import Optional

from app.config import settings
from app.crawlers.base import BaseJobCrawler
from app.crawlers.itviec import ITviecCrawler
from app.crawlers.playwright_browser import PlaywrightJobCrawler
from app.crawlers.topcv import TopCVCrawler
from app.crawlers.topdev import TopDevCrawler
from app.crawlers.vietnamworks import VietnamWorksCrawler
from app.database import get_db_session, init_db
from app.models import CrawlRun
from app.repository import create_crawl_run, finish_crawl_run, upsert_jobs

logger = logging.getLogger(__name__)


def get_enabled_crawlers(source_filter: Optional[str] = None) -> list[BaseJobCrawler]:
    """Trả về danh sách các crawler được kích hoạt."""
    topcv_crawler = (
        PlaywrightJobCrawler(
            target_site="topcv",
            headless=settings.playwright_headless,
            max_pages=settings.topcv_max_pages,
        )
        if settings.use_playwright
        else TopCVCrawler()
    )

    itviec_crawler = (
        PlaywrightJobCrawler(
            target_site="itviec",
            headless=settings.playwright_headless,
            max_pages=settings.itviec_max_pages,
        )
        if settings.use_playwright
        else ITviecCrawler()
    )

    registry: dict[str, BaseJobCrawler] = {
        "vietnamworks": VietnamWorksCrawler(),
        "topdev": TopDevCrawler(),
        "topcv": topcv_crawler,
        "itviec": itviec_crawler,
        "topcv_pw": PlaywrightJobCrawler(
            target_site="topcv",
            headless=settings.playwright_headless,
            max_pages=settings.topcv_max_pages,
        ),
        "itviec_pw": PlaywrightJobCrawler(
            target_site="itviec",
            headless=settings.playwright_headless,
            max_pages=settings.itviec_max_pages,
        ),
    }

    if source_filter:
        target = source_filter.strip().lower()
        return [registry[target]] if target in registry else []

    return [
        crawler
        for key, crawler in registry.items()
        if key in settings.enabled_sources
    ]


def run_daily_crawl(source_filter: Optional[str] = None) -> None:
    """Khởi tạo bảng (nếu chưa có), chạy lần lượt từng crawler và lưu kết quả vào PostgreSQL."""
    init_db()
    crawlers = get_enabled_crawlers(source_filter)
    if not crawlers:
        logger.warning("Không tìm thấy crawler nào khớp với bộ lọc: %s", source_filter)
        return

    for crawler in crawlers:
        source_name = crawler.source_name
        logger.info("=== Bắt đầu chu kỳ crawl nguồn: %s ===", source_name)

        with get_db_session() as session:
            run_record = create_crawl_run(session, source=source_name)
            run_id = run_record.id

        try:
            jobs = crawler.crawl()
            total_fetched = len(jobs)

            with get_db_session() as session:
                inserted, updated = upsert_jobs(session, jobs)
                run_obj = session.get(CrawlRun, run_id)
                if run_obj:
                    finish_crawl_run(
                        session,
                        run_obj,
                        status="SUCCESS",
                        total_fetched=total_fetched,
                        inserted_count=inserted,
                        updated_count=updated,
                    )

            logger.info(
                "=== Hoàn tất %s: Thu thập=%d | Thêm mới=%d | Cập nhật=%d ===",
                source_name,
                total_fetched,
                inserted,
                updated,
            )
        except Exception as exc:
            logger.exception("Lỗi trong quá trình crawl nguồn %s: %s", source_name, exc)
            with get_db_session() as session:
                run_obj = session.get(CrawlRun, run_id)
                if run_obj:
                    finish_crawl_run(
                        session,
                        run_obj,
                        status="FAILED",
                        total_fetched=0,
                        inserted_count=0,
                        updated_count=0,
                        error_message=str(exc),
                    )
