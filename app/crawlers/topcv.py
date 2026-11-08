import logging
import time
from typing import Any, Optional

from bs4 import BeautifulSoup
import httpx

from app.config import settings
from app.crawlers.base import BaseJobCrawler
from app.crawlers.topdev import parse_salary_string

logger = logging.getLogger(__name__)


def is_anti_bot_challenged(resp: httpx.Response) -> bool:
    """Kiểm tra phản hồi có bị chặn bởi cổng xác thực chống bot / CAPTCHA hay không."""
    if resp.status_code in (403, 429, 503):
        return True
    if resp.headers.get("cf-mitigated") == "challenge":
        return True
    text_sample = resp.text[:4000].lower()
    if "just a moment..." in text_sample or "cf-turnstile" in text_sample or "verify you are human" in text_sample:
        return True
    return False


class TopCVCrawler(BaseJobCrawler):
    """
    Crawler thu thập danh sách việc làm IT công khai từ TopCV.
    Lưu ý: Nếu TopCV bật cổng xác thực Cloudflare/CAPTCHA đối với kết nối tự động,
    crawler sẽ dừng ngay lập tức và thông báo để người dùng sử dụng Chrome Extension.
    """

    source_name = "TopCV"
    LISTING_URL = "https://www.topcv.vn/tim-viec-lam-cong-nghe-thong-tin-cr257"

    def __init__(
        self,
        max_pages: Optional[int] = None,
        delay_sec: Optional[float] = None,
    ) -> None:
        self.max_pages = max_pages if max_pages is not None else settings.topcv_max_pages
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
        job_cards = soup.select(".job-item-search-result, .job-item-2, .job-item-default")
        results: list[dict[str, Any]] = []

        for card in job_cards:
            title_link = card.select_one("h3.title a[href], .title-block a[href], a[href*='/viec-lam/']")
            if not title_link:
                continue

            title = title_link.get_text(strip=True)
            href = (title_link.get("href") or "").strip()
            if not title or not href:
                continue

            job_url = href.split("?")[0] if "topcv.vn/viec-lam/" in href else href
            job_id = card.get("data-job-id")

            company_el = card.select_one("a.company, .company-name, [class*='company']")
            company_name = company_el.get_text(strip=True) if company_el else None

            logo_el = card.select_one("img[src]")
            company_logo = logo_el.get("src") if logo_el else None

            salary_el = card.select_one(".title-salary, .salary, [class*='salary']")
            salary_text = salary_el.get_text(strip=True) if salary_el else None
            sal_min, sal_max, currency = parse_salary_string(salary_text)

            loc_el = card.select_one(".address, .location, [class*='address']")
            location = loc_el.get_text(strip=True) if loc_el else None

            skills = [
                tag.get_text(strip=True)
                for tag in card.select(".tag-skill, .skills .item, .label-skill")
                if tag.get_text(strip=True)
            ]

            results.append(
                {
                    "source": self.source_name,
                    "external_id": str(job_id) if job_id else None,
                    "title": title,
                    "company_name": company_name,
                    "company_logo": company_logo,
                    "location": location,
                    "salary_min": sal_min,
                    "salary_max": sal_max,
                    "currency": currency,
                    "salary_text": salary_text,
                    "job_url": job_url,
                    "description": None,
                    "requirements": None,
                    "benefits": None,
                    "skills": skills,
                    "job_level": None,
                    "working_type": None,
                    "posted_at": None,
                    "expired_at": None,
                    "raw_data": {"job_url": job_url, "salary_text": salary_text},
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
                        "[%s] Trang đích yêu cầu xác thực chống bot / CAPTCHA (HTTP %d). "
                        "Dừng thu thập tự động nguồn TopCV; bạn có thể đẩy dữ liệu từ Chrome Extension qua API.",
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

