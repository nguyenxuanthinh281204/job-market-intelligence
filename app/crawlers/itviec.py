import logging
import time
from typing import Any, Optional

from bs4 import BeautifulSoup
import httpx

from app.config import settings
from app.crawlers.base import BaseJobCrawler
from app.crawlers.topcv import is_anti_bot_challenged

logger = logging.getLogger(__name__)


class ITviecCrawler(BaseJobCrawler):
    """
    Crawler thu thập việc làm IT từ ITviec.
    Lưu ý: ITviec thường bật Cloudflare bảo vệ. Khi gặp cổng xác thực chống bot / CAPTCHA,
    crawler sẽ dừng ngay lập tức và báo trạng thái mà không can thiệp vượt cổng bảo vệ.
    """

    source_name = "ITviec"
    LISTING_URL = "https://itviec.com/it-jobs"

    def __init__(
        self,
        max_pages: Optional[int] = None,
        delay_sec: Optional[float] = None,
    ) -> None:
        self.max_pages = max_pages if max_pages is not None else settings.itviec_max_pages
        self.delay_sec = delay_sec if delay_sec is not None else settings.request_delay_sec
        self.headers = {
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
            "Accept-Language": "vi-VN,vi;q=0.9,en-US;q=0.8,en;q=0.7",
            "User-Agent": (
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/125.0.0.0 Safari/537.36"
            ),
        }

    def _parse_listing_html(self, html: str) -> list[dict[str, Any]]:
        soup = BeautifulSoup(html, "html.parser")
        job_cards = soup.select(".job-card, [data-search--job-selection-job-slug-value], .ipy-2")
        results: list[dict[str, Any]] = []

        for card in job_cards:
            title_link = card.select_one("h3 a[href*='/it-jobs/'], a[href*='/it-jobs/']")
            if not title_link:
                continue

            title = title_link.get_text(strip=True)
            href = (title_link.get("href") or "").strip()
            if not title or not href:
                continue

            job_url = f"https://itviec.com{href}" if href.startswith("/") else href
            job_url = job_url.split("?")[0]

            company_el = card.select_one(".company-name, a[href*='/companies/']")
            company_name = company_el.get_text(strip=True) if company_el else None

            loc_el = card.select_one(".city, .text-rich-grey")
            location = loc_el.get_text(strip=True) if loc_el else None

            skills = [
                tag.get_text(strip=True)
                for tag in card.select(".itag, a[href*='/it-jobs/'] .tag")
                if tag.get_text(strip=True)
            ]

            results.append(
                {
                    "source": self.source_name,
                    "external_id": card.get("data-search--job-selection-job-id-value"),
                    "title": title,
                    "company_name": company_name,
                    "company_logo": None,
                    "location": location,
                    "salary_min": None,
                    "salary_max": None,
                    "currency": "USD",
                    "salary_text": None,
                    "job_url": job_url,
                    "description": None,
                    "requirements": None,
                    "benefits": None,
                    "skills": skills,
                    "job_level": None,
                    "working_type": None,
                    "posted_at": None,
                    "expired_at": None,
                    "raw_data": {"job_url": job_url},
                }
            )

        return results

    def crawl(self) -> list[dict[str, Any]]:
        jobs_by_url: dict[str, dict[str, Any]] = {}

        with httpx.Client(headers=self.headers, timeout=30.0, follow_redirects=True) as client:
            for page in range(1, self.max_pages + 1):
                url = self.LISTING_URL if page == 1 else f"{self.LISTING_URL}?page={page}"
                try:
                    resp = client.get(url)
                except Exception as exc:
                    logger.error("[%s] Lỗi kết nối tại trang %d: %s", self.source_name, page, exc)
                    break

                if is_anti_bot_challenged(resp):
                    logger.warning(
                        "[%s] Trang đích yêu cầu xác thực chống bot / Cloudflare (HTTP %d). "
                        "Dừng thu thập tự động nguồn ITviec.",
                        self.source_name,
                        resp.status_code,
                    )
                    break

                parsed_jobs = self._parse_listing_html(resp.text)
                if not parsed_jobs:
                    logger.info("[%s] Không tìm thấy job nào tại trang %d.", self.source_name, page)
                    break

                for job in parsed_jobs:
                    jobs_by_url[job["job_url"]] = job

                logger.info(
                    "[%s] Trang %d/%d: thu được %d job (Tổng cộng: %d)",
                    self.source_name,
                    page,
                    self.max_pages,
                    len(parsed_jobs),
                    len(jobs_by_url),
                )
                time.sleep(self.delay_sec)

        return list(jobs_by_url.values())

