import logging
import re
import time
from typing import Any, Optional

import httpx

from app.config import settings
from app.crawlers.base import BaseJobCrawler, safe_float
from app.crawlers.vietnamworks import clean_html, parse_iso_or_epoch

logger = logging.getLogger(__name__)


def parse_salary_string(salary_text: Optional[str]) -> tuple[Optional[float], Optional[float], str]:
    """Phân tích chuỗi mức lương (VND / USD) thành (salary_min, salary_max, currency)."""
    if not salary_text:
        return None, None, "VND"

    text = salary_text.lower().replace(",", "").strip()
    if any(k in text for k in ("thỏa thuận", "thoả thuận", "negotiable", "cạnh tranh")):
        return None, None, "VND"

    currency = "USD" if ("usd" in text or "$" in text) else "VND"
    multiplier = 1.0
    if currency == "VND" and any(k in text for k in ("tr", "triệu", "million", "m")):
        multiplier = 1_000_000.0

    numbers = [float(m) for m in re.findall(r"\d+(?:\.\d+)?", text)]
    if not numbers:
        return None, None, currency

    amounts = [n * multiplier for n in numbers]
    if any(k in text for k in ("upto", "up to", "tối đa", "đến", "dưới")):
        return None, amounts[0], currency
    if any(k in text for k in ("từ", "trên", "from", "over")):
        return amounts[0], None, currency
    if len(amounts) >= 2:
        return min(amounts), max(amounts), currency
    return amounts[0], amounts[0], currency


class TopDevCrawler(BaseJobCrawler):
    """
    Crawler thu thập việc làm IT từ API công khai của TopDev.
    Endpoint: https://api.topdev.vn/td/v2/jobs
    """

    source_name = "TopDev"
    API_URL = "https://api.topdev.vn/td/v2/jobs"

    def __init__(
        self,
        max_pages: Optional[int] = None,
        page_size: Optional[int] = None,
        delay_sec: Optional[float] = None,
    ) -> None:
        self.max_pages = max_pages if max_pages is not None else settings.topdev_max_pages
        self.page_size = page_size if page_size is not None else settings.topdev_page_size
        self.delay_sec = delay_sec if delay_sec is not None else settings.request_delay_sec
        self.headers = {
            "Accept": "application/json, text/plain, */*",
            "Origin": "https://topdev.vn",
            "Referer": "https://topdev.vn/viec-lam-it",
            "User-Agent": (
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/125.0.0.0 Safari/537.36"
            ),
        }

    def _normalize_job(self, item: dict[str, Any]) -> Optional[dict[str, Any]]:
        job_id = item.get("id")
        title = (item.get("title") or "").strip()
        if not title:
            return None

        job_url = (item.get("detail_url") or item.get("url") or "").strip()
        if not job_url:
            slug = (item.get("slug") or "").strip()
            if slug:
                job_url = f"https://topdev.vn/detail-jobs/{slug}"
            else:
                return None

        # Công ty
        company_obj = item.get("company") if isinstance(item.get("company"), dict) else {}
        company_name = (
            company_obj.get("display_name")
            or company_obj.get("name")
            or item.get("company_name")
            or ""
        ).strip() or None
        company_logo = company_obj.get("image_logo") or item.get("company_logo") or None

        # Địa điểm
        addresses = item.get("addresses") if isinstance(item.get("addresses"), dict) else {}
        full_addrs = addresses.get("full_addresses") or addresses.get("address_region_list") or []
        if isinstance(full_addrs, list) and full_addrs:
            location = ", ".join(str(a).strip() for a in full_addrs if a)
        else:
            location = (company_obj.get("address") or "").strip() or None

        # Lương
        salary_obj = item.get("salary") if isinstance(item.get("salary"), dict) else {}
        salary_text = (
            salary_obj.get("value")
            or item.get("salary_value")
            or None
        )
        sal_min = salary_obj.get("min")
        sal_max = salary_obj.get("max")
        currency = (salary_obj.get("currency") or "VND").upper()

        salary_min_val = safe_float(sal_min)
        salary_max_val = safe_float(sal_max)
        if salary_min_val is None and salary_max_val is None and salary_text:
            salary_min_val, salary_max_val, currency = parse_salary_string(str(salary_text))

        # Kỹ năng
        raw_skills = item.get("skills_arr") or item.get("skills_str") or item.get("skills") or []
        skills: list[str] = []
        if isinstance(raw_skills, list):
            for sk in raw_skills:
                if isinstance(sk, str) and sk.strip():
                    skills.append(sk.strip())
                elif isinstance(sk, dict):
                    name = sk.get("name") or sk.get("title")
                    if name:
                        skills.append(str(name).strip())
        elif isinstance(raw_skills, str):
            skills = [s.strip() for s in raw_skills.split(",") if s.strip()]

        # Phúc lợi
        raw_benefits = item.get("benefits") or []
        benefit_lines: list[str] = []
        if isinstance(raw_benefits, list):
            for bf in raw_benefits:
                if isinstance(bf, dict) and bf.get("value"):
                    benefit_lines.append(str(bf["value"]).strip())
                elif isinstance(bf, str) and bf.strip():
                    benefit_lines.append(bf.strip())
        benefits_text = "\n".join(benefit_lines) if benefit_lines else None

        description = clean_html(item.get("description") or item.get("content"))
        requirements = clean_html(item.get("requirements"))

        published_val = item.get("published")
        published_dt = None
        if isinstance(published_val, dict):
            published_dt = published_val.get("datetime") or published_val.get("date")
        elif published_val:
            published_dt = published_val
        else:
            published_dt = item.get("published_at") or item.get("refreshed_at")
        posted_at = parse_iso_or_epoch(published_dt)

        return {
            "source": self.source_name,
            "external_id": str(job_id) if job_id is not None else None,
            "title": title,
            "company_name": company_name,
            "company_logo": company_logo,
            "location": location,
            "salary_min": salary_min_val,
            "salary_max": salary_max_val,
            "currency": currency,
            "salary_text": str(salary_text) if salary_text else None,
            "job_url": job_url,
            "description": description,
            "requirements": requirements,
            "benefits": benefits_text,
            "skills": skills,
            "job_level": item.get("job_levels_str") or None,
            "working_type": item.get("job_types_str") or None,
            "posted_at": posted_at,
            "expired_at": None,
            "raw_data": item,
        }

    def crawl(self) -> list[dict[str, Any]]:
        jobs_by_url: dict[str, dict[str, Any]] = {}
        fields_job = (
            "id,title,slug,company,salary,addresses,skills_arr,skills_str,"
            "job_levels_str,job_types_str,description,requirements,benefits,"
            "detail_url,published,refreshed_at"
        )

        with httpx.Client(headers=self.headers, timeout=30.0, follow_redirects=True) as client:
            for page in range(1, self.max_pages + 1):
                params = {
                    "page": page,
                    "per_page": self.page_size,
                    "fields[job]": fields_job,
                    "fields[company]": "name,display_name,image_logo,address",
                    "locale": "vi_VN",
                }
                try:
                    resp = client.get(self.API_URL, params=params)
                    if resp.status_code in (403, 429):
                        logger.warning(
                            "[%s] Máy chủ trả về HTTP %d tại trang %d. Dừng thu thập nguồn này để tuân thủ giới hạn truy cập.",
                            self.source_name,
                            resp.status_code,
                            page,
                        )
                        break
                    resp.raise_for_status()
                    body = resp.json()
                except Exception as exc:
                    logger.error("[%s] Lỗi khi tải trang %d: %s", self.source_name, page, exc)
                    break

                data_list = body.get("data") or []
                if not data_list:
                    logger.info("[%s] Không còn dữ liệu tại trang %d.", self.source_name, page)
                    break

                page_count = 0
                for raw_job in data_list:
                    normalized = self._normalize_job(raw_job)
                    if normalized and normalized["job_url"]:
                        jobs_by_url[normalized["job_url"]] = normalized
                        page_count += 1

                meta = body.get("meta") or {}
                last_page = meta.get("last_page") or self.max_pages

                logger.info(
                    "[%s] Trang %d/%d: thu được %d job (Tổng cộng: %d)",
                    self.source_name,
                    page,
                    min(self.max_pages, int(last_page)),
                    page_count,
                    len(jobs_by_url),
                )

                if page >= int(last_page):
                    break

                time.sleep(self.delay_sec)

        return list(jobs_by_url.values())

