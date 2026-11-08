import logging
import time
from typing import Any, Optional

from app.config import settings
from app.crawlers.base import BaseJobCrawler, safe_float
from app.crawlers.topdev import parse_salary_string

logger = logging.getLogger(__name__)


class PlaywrightJobCrawler(BaseJobCrawler):
    """
    Trình thu thập dữ liệu bằng trình duyệt Chromium ngầm (Playwright)
    dành cho các trang có JavaScript phức tạp hoặc bảo vệ chống bot (TopCV, ITviec).
    """

    source_name = "Playwright"

    def __init__(
        self,
        target_site: str = "itviec",  # "itviec" hoặc "topcv"
        headless: bool = True,
        max_pages: int = 3,
    ) -> None:
        self.target_site = target_site.lower()
        self.headless = headless
        self.max_pages = max_pages
        self.source_name = "ITviec" if self.target_site == "itviec" else "TopCV"

    def crawl(self) -> list[dict[str, Any]]:
        try:
            from playwright.sync_api import sync_playwright
        except ImportError:
            logger.error(
                "Chưa cài đặt thư viện Playwright. "
                "Vui lòng chạy: pip install playwright && playwright install chromium"
            )
            return []

        jobs: list[dict[str, Any]] = []

        with sync_playwright() as p:
            # Khởi tạo Chromium với các tùy chọn ẩn danh danh tính bot (stealth)
            browser = p.chromium.launch(
                headless=self.headless,
                args=[
                    "--disable-blink-features=AutomationControlled",
                    "--no-sandbox",
                    "--disable-setuid-sandbox",
                    "--disable-dev-shm-usage",
                ],
            )
            context = browser.new_context(
                user_agent=(
                    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                    "AppleWebKit/537.36 (KHTML, like Gecko) "
                    "Chrome/125.0.0.0 Safari/537.36"
                ),
                viewport={"width": 1920, "height": 1080},
                locale="vi-VN",
            )
            page = context.new_page()

            if self.target_site == "itviec":
                jobs = self._crawl_itviec(page)
            else:
                jobs = self._crawl_topcv(page)

            browser.close()

        return jobs

    def _crawl_itviec(self, page) -> list[dict[str, Any]]:
        logger.info("[ITviec - Playwright] Đang truy cập danh sách việc làm IT...")
        jobs_map: dict[str, dict[str, Any]] = {}

        for p_idx in range(1, self.max_pages + 1):
            url = f"https://itviec.com/it-jobs?page={p_idx}"
            try:
                page.goto(url, wait_until="domcontentloaded", timeout=45000)
                # Chờ các card việc làm xuất hiện
                page.wait_for_timeout(3000)
            except Exception as e:
                logger.warning("[ITviec - Playwright] Lỗi khi tải trang %d: %s", p_idx, e)
                break

            # Kiểm tra xem có bị Cloudflare Challenge không
            title = page.title()
            if "Just a moment" in title or "Attention Required" in title:
                logger.warning(
                    "[ITviec - Playwright] Gặp cổng bảo vệ Cloudflare. Đang chờ 5s để trình duyệt tự giải..."
                )
                page.wait_for_timeout(5000)

            cards = page.query_selector_all(".job-card, [data-search--job-selection-job-slug-value]")
            if not cards:
                logger.info("[ITviec - Playwright] Không tìm thấy thêm việc làm tại trang %d.", p_idx)
                break

            for card in cards:
                try:
                    title_el = card.query_selector("h3 a[href*='/it-jobs/'], a[href*='/it-jobs/']")
                    if not title_el:
                        continue
                    title_text = title_el.inner_text().strip()
                    href = title_el.get_attribute("href") or ""
                    if not href.startswith("http"):
                        href = f"https://itviec.com{href}"
                    job_url = href.split("?")[0]

                    company_el = card.query_selector(".company-name, a[href*='/companies/']")
                    company_name = company_el.inner_text().strip() if company_el else None

                    loc_el = card.query_selector(".city, .text-rich-grey")
                    location = loc_el.inner_text().strip() if loc_el else None

                    skills = [
                        tag.inner_text().strip()
                        for tag in card.query_selector_all(".itag, a[href*='/it-jobs/'] .tag")
                        if tag.inner_text().strip()
                    ]

                    jobs_map[job_url] = {
                        "source": "ITviec",
                        "external_id": None,
                        "title": title_text,
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
                        "raw_data": {"job_url": job_url, "source": "playwright"},
                    }
                except Exception as ex:
                    logger.debug("Lỗi đọc card job: %s", ex)

            logger.info(
                "[ITviec - Playwright] Trang %d: lấy được %d job (Tổng cộng: %d)",
                p_idx,
                len(cards),
                len(jobs_map),
            )
            time.sleep(2)

        return list(jobs_map.values())

    def _crawl_topcv(self, page) -> list[dict[str, Any]]:
        logger.info("[TopCV - Playwright] Đang truy cập việc làm IT...")
        jobs_map: dict[str, dict[str, Any]] = {}

        for p_idx in range(1, self.max_pages + 1):
            url = f"https://www.topcv.vn/tim-viec-lam-cong-nghe-thong-tin-cr257?page={p_idx}"
            try:
                page.goto(url, wait_until="domcontentloaded", timeout=45000)
                page.wait_for_timeout(3000)
            except Exception as e:
                logger.warning("[TopCV - Playwright] Lỗi khi tải trang %d: %s", p_idx, e)
                break

            cards = page.query_selector_all(".job-item-search-result, .job-item-2, .job-item-default")
            if not cards:
                logger.info("[TopCV - Playwright] Hết việc làm tại trang %d.", p_idx)
                break

            for card in cards:
                try:
                    title_link = card.query_selector("h3.title a[href], .title-block a[href], a[href*='/viec-lam/']")
                    if not title_link:
                        continue
                    title_text = title_link.inner_text().strip()
                    href = title_link.get_attribute("href") or ""
                    job_url = href.split("?")[0]

                    company_el = card.query_selector("a.company, .company-name, [class*='company']")
                    company_name = company_el.inner_text().strip() if company_el else None

                    salary_el = card.query_selector(".title-salary, .salary, [class*='salary']")
                    salary_text = salary_el.inner_text().strip() if salary_el else None
                    sal_min, sal_max, currency = parse_salary_string(salary_text)

                    loc_el = card.query_selector(".address, .location, [class*='address']")
                    location = loc_el.inner_text().strip() if loc_el else None

                    skills = [
                        tag.inner_text().strip()
                        for tag in card.query_selector_all(".tag-skill, .skills .item, .label-skill")
                        if tag.inner_text().strip()
                    ]

                    jobs_map[job_url] = {
                        "source": "TopCV",
                        "external_id": None,
                        "title": title_text,
                        "company_name": company_name,
                        "company_logo": None,
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
                        "raw_data": {"job_url": job_url, "source": "playwright"},
                    }
                except Exception as ex:
                    logger.debug("Lỗi đọc card TopCV: %s", ex)

            logger.info(
                "[TopCV - Playwright] Trang %d: lấy được %d job (Tổng cộng: %d)",
                p_idx,
                len(cards),
                len(jobs_map),
            )
            time.sleep(2)

        return list(jobs_map.values())

