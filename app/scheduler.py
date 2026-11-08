import logging
import signal
import sys

from apscheduler.schedulers.blocking import BlockingScheduler
from apscheduler.triggers.cron import CronTrigger

from app.config import settings
from app.pipeline import run_daily_crawl

logger = logging.getLogger(__name__)


def start_scheduler() -> None:
    """Khởi chạy trình lập lịch tự động hàng ngày với APScheduler."""
    if settings.run_on_startup:
        logger.info("RUN_ON_STARTUP=true -> Chạy thu thập dữ liệu ngay khi khởi động...")
        run_daily_crawl()

    scheduler = BlockingScheduler(timezone=settings.timezone)

    trigger = CronTrigger(
        hour=settings.crawl_cron_hour,
        minute=settings.crawl_cron_minute,
        timezone=settings.timezone,
    )

    scheduler.add_job(
        run_daily_crawl,
        trigger=trigger,
        id="daily_it_job_crawl",
        name="Thu thập dữ liệu việc làm IT hàng ngày",
        replace_existing=True,
        max_instances=1,
        coalesce=True,
    )

    def _shutdown(signum, frame):
        logger.info("Nhận tín hiệu dừng (%s). Đang tắt scheduler...", signum)
        scheduler.shutdown(wait=False)
        sys.exit(0)

    signal.signal(signal.SIGINT, _shutdown)
    signal.signal(signal.SIGTERM, _shutdown)

    logger.info(
        "Đã kích hoạt Cron Scheduler! Lịch chạy tự động hàng ngày lúc %02d:%02d (%s).",
        settings.crawl_cron_hour,
        settings.crawl_cron_minute,
        settings.timezone,
    )
    scheduler.start()

