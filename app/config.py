import os
from dataclasses import dataclass, field
from dotenv import load_dotenv

load_dotenv()


def _parse_csv(raw: str) -> list[str]:
    return [item.strip() for item in raw.split(",") if item.strip()]


@dataclass
class Settings:
    database_url: str = field(
        default_factory=lambda: os.getenv(
            "DATABASE_URL",
            "postgresql+psycopg2://postgres:postgres@localhost:5433/job_crawl",
        )
    )
    timezone: str = field(
        default_factory=lambda: os.getenv("TIMEZONE", "Asia/Ho_Chi_Minh")
    )
    crawl_cron_hour: int = field(
        default_factory=lambda: int(os.getenv("CRAWL_CRON_HOUR", "8"))
    )
    crawl_cron_minute: int = field(
        default_factory=lambda: int(os.getenv("CRAWL_CRON_MINUTE", "0"))
    )
    run_on_startup: bool = field(
        default_factory=lambda: os.getenv("RUN_ON_STARTUP", "true").lower()
        in ("1", "true", "yes")
    )
    enabled_sources: list[str] = field(
        default_factory=lambda: [
            s.lower()
            for s in _parse_csv(os.getenv("ENABLED_SOURCES", "vietnamworks,topdev"))
        ]
    )
    request_delay_sec: float = field(
        default_factory=lambda: float(os.getenv("REQUEST_DELAY_SEC", "1.5"))
    )

    # VietnamWorks config
    vnw_max_pages: int = field(
        default_factory=lambda: int(os.getenv("VNW_MAX_PAGES", "5"))
    )
    vnw_page_size: int = field(
        default_factory=lambda: int(os.getenv("VNW_PAGE_SIZE", "50"))
    )
    vnw_request_delay_sec: float = field(
        default_factory=lambda: float(os.getenv("VNW_REQUEST_DELAY_SEC", "1.5"))
    )
    vnw_keywords: list[str] = field(
        default_factory=lambda: _parse_csv(
            os.getenv(
                "VNW_KEYWORDS",
                "Developer,Software Engineer,Data Engineer,DevOps,Backend,Frontend,Fullstack,AI Engineer,QA QC",
            )
        )
    )

    # TopDev / TopCV / ITviec config
    topdev_max_pages: int = field(
        default_factory=lambda: int(os.getenv("TOPDEV_MAX_PAGES", "5"))
    )
    topdev_page_size: int = field(
        default_factory=lambda: int(os.getenv("TOPDEV_PAGE_SIZE", "30"))
    )
    topcv_max_pages: int = field(
        default_factory=lambda: int(os.getenv("TOPCV_MAX_PAGES", "3"))
    )
    itviec_max_pages: int = field(
        default_factory=lambda: int(os.getenv("ITVIEC_MAX_PAGES", "3"))
    )
    use_playwright: bool = field(
        default_factory=lambda: os.getenv("USE_PLAYWRIGHT", "true").lower() in ("1", "true", "yes")
    )
    playwright_headless: bool = field(
        default_factory=lambda: os.getenv("PLAYWRIGHT_HEADLESS", "true").lower() in ("1", "true", "yes")
    )


settings = Settings()
