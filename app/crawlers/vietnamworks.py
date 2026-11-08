from datetime import datetime, timezone
import logging
import time
from typing import Any, Optional

from bs4 import BeautifulSoup
import httpx

from app.config import settings
from app.crawlers.base import BaseJobCrawler, safe_float

logger = logging.getLogger(__name__)


def clean_html(raw_html: Optional[str]) -> Optional[str]:
    """Loại bỏ thẻ HTML và chuẩn hóa khoảng trắng."""
    if not raw_html:
        return None
    soup = BeautifulSoup(raw_html, "html.parser")
    text = soup.get_text(separator="\n", strip=True)
    return text or None


def parse_iso_or_epoch(val: Any) -> Optional[datetime]:
    """Chuyển đổi timestamp hoặc chuỗi ISO 8601 sang datetime có timezone."""
    if not val:
        return None
    if isinstance(val, (int, float)):
        ts = val / 1000.0 if val > 1e11 else float(val)
        return datetime.fromtimestamp(ts, tz=timezone.utc)
    if isinstance(val, str):
        val_str = val.strip()
        if not val_str:
            return None
        if val_str.isdigit():
            num = float(val_str)
            ts = num / 1000.0 if num > 1e11 else num
            return datetime.fromtimestamp(ts, tz=timezone.utc)
        try:
            cleaned = val_str.replace("Z", "+00:00")
            dt = datetime.fromisoformat(cleaned)
            if dt.tzinfo is None:
                dt = dt.replace(tzinfo=timezone.utc)
            return dt
        except ValueError:
            return None
    return None


class VietnamWorksCrawler(BaseJobCrawler):
    """
    Crawler thu thập việc làm IT từ API tìm kiếm công khai của VietnamWorks.
    Endpoint: https://ms.vietnamworks.com/job-search/v1.0/search
    """

    source_name = "VietnamWorks"
    SEARCH_API_URL = "https://ms.vietnamworks.com/job-search/v1.0/search"

    def __init__(
        self,
        keywords: Optional[list[str]] = None,
        max_pages: Optional[int] = None,
        page_size: Optional[int] = None,
        delay_sec: Optional[float] = None,
    ) -> None:
        self.keywords = keywords if keywords is not None else settings.vnw_keywords
        self.max_pages = max_pages if max_pages is not None else settings.vnw_max_pages
        self.page_size = page_size if page_size is not None else settings.vnw_page_size
        self.delay_sec = (
            delay_sec if delay_sec is not None else settings.vnw_request_delay_sec
        )
        self.headers = {
            "Accept": "application/json, text/plain, */*",
            "Content-Type": "application/json",
            "Origin": "https://www.vietnamworks.com",
            "Referer": "https://www.vietnamworks.com/",
            "User-Agent": (
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/125.0.0.0 Safari/537.36"
            ),
        }

    def _build_payload(self, query: str, page: int) -> dict[str, Any]:
        return {
            "userId": 0,
            "query": query,
            "filter": [],
            "ranges": [],
            "order": [{"field": "approvedOn", "value": "desc"}],
            "hitsPerPage": self.page_size,
            "page": page,
            "retrieveFields": [
                "address",
                "benefits",
                "companyId",
                "companyLogo",
                "companyName",
                "expiredOn",
                "isSalaryVisible",
                "jobDescription",
                "jobId",
                "jobLevel",
                "jobLevelVI",
                "jobRequirement",
                "jobTitle",
                "jobUrl",
                "alias",
                "onlineOn",
                "approvedOn",
                "prettySalary",
                "salary",
                "salaryCurrency",
                "salaryMax",
                "salaryMin",
                "skills",
                "workingLocations",
                "typeWorkingId",
            ],
        }

    def _normalize_job(self, item: dict[str, Any]) -> Optional[dict[str, Any]]:
        job_id = item.get("jobId")
        title = (item.get("jobTitle") or "").strip()
        if not title:
            return None

        # Xây dựng URL chuẩn của VietnamWorks
        job_url = (item.get("jobUrl") or "").strip()
        if not job_url:
            alias = (item.get("alias") or "viec-lam-it").strip()
            if job_id:
                job_url = f"https://www.vietnamworks.com/{alias}-{job_id}-jv"
            else:
                return None
        elif job_url.startswith("/"):
            job_url = f"https://www.vietnamworks.com{job_url}"

        # Địa điểm làm việc
        working_locations = item.get("workingLocations") or []
        loc_names: list[str] = []
        if isinstance(working_locations, list):
            for loc in working_locations:
                if isinstance(loc, dict):
                    city_name = (
                        loc.get("cityNameVI")
                        or loc.get("cityName")
                        or loc.get("address")
                    )
                    if city_name and city_name not in loc_names:
                        loc_names.append(str(city_name).strip())
        location = ", ".join(loc_names) if loc_names else (item.get("address") or None)

        # Lương
        salary_min = item.get("salaryMin")
        salary_max = item.get("salaryMax")
        salary_min_val = safe_float(salary_min)
        salary_max_val = safe_float(salary_max)
        currency = (item.get("salaryCurrency") or "USD").upper()
        salary_text = item.get("prettySalary") or None

        # Kỹ năng (skills)
        raw_skills = item.get("skills") or []
        skills: list[str] = []
        if isinstance(raw_skills, list):
            for sk in raw_skills:
                if isinstance(sk, dict):
                    sk_name = sk.get("skillName") or sk.get("name")
                    if sk_name:
                        skills.append(str(sk_name).strip())
                elif isinstance(sk, str) and sk.strip():
                    skills.append(sk.strip())

        # Phúc lợi (benefits)
        raw_benefits = item.get("benefits") or []
        benefit_lines: list[str] = []
        if isinstance(raw_benefits, list):
            for bf in raw_benefits:
                if isinstance(bf, dict):
                    bf_val = bf.get("benefitValue") or bf.get("benefitNameVI") or bf.get("benefitName")
                    if bf_val:
                        benefit_lines.append(str(bf_val).strip())
        benefits_text = "\n".join(benefit_lines) if benefit_lines else None

        description = clean_html(item.get("jobDescription"))
        requirements = clean_html(item.get("jobRequirement"))
        posted_at = parse_iso_or_epoch(item.get("approvedOn") or item.get("onlineOn"))
        expired_at = parse_iso_or_epoch(item.get("expiredOn"))

        return {
            "source": self.source_name,
            "external_id": str(job_id) if job_id is not None else None,
            "title": title,
            "company_name": (item.get("companyName") or "").strip() or None,
            "company_logo": item.get("companyLogo") or None,
            "location": location,
            "salary_min": salary_min_val,
            "salary_max": salary_max_val,
            "currency": currency,
            "salary_text": salary_text,
            "job_url": job_url,
            "description": description,
            "requirements": requirements,
            "benefits": benefits_text,
            "skills": skills,
            "job_level": item.get("jobLevelVI") or item.get("jobLevel") or None,
            "working_type": str(item.get("typeWorkingId")) if item.get("typeWorkingId") else None,
            "posted_at": posted_at,
            "expired_at": expired_at,
            "raw_data": item,
        }

    def crawl(self) -> list[dict[str, Any]]:
        """Chạy thu thập dữ liệu qua danh sách từ khóa IT và phân trang."""
        jobs_by_url: dict[str, dict[str, Any]] = {}

        with httpx.Client(headers=self.headers, timeout=30.0, follow_redirects=True) as client:
            for kw_idx, keyword in enumerate(self.keywords):
                logger.info(
                    "[%s] Đang tìm kiếm từ khóa '%s' (%d/%d)...",
                    self.source_name,
                    keyword,
                    kw_idx + 1,
                    len(self.keywords),
                )

                for page in range(self.max_pages):
                    payload = self._build_payload(query=keyword, page=page)
                    try:
                        resp = client.post(self.SEARCH_API_URL, json=payload)
                        resp.raise_for_status()
                        body = resp.json()
                    except Exception as exc:
                        logger.error(
                            "[%s] Lỗi khi gọi API (keyword='%s', page=%d): %s",
                            self.source_name,
                            keyword,
                            page,
                            exc,
                        )
                        break

                    data_list = body.get("data") or []
                    meta = body.get("meta") or {}
                    nb_pages = meta.get("nbPages", 1)

                    if not data_list:
                        logger.info(
                            "[%s] Từ khóa '%s' hết dữ liệu tại trang %d.",
                            self.source_name,
                            keyword,
                            page,
                        )
                        break

                    page_count = 0
                    for raw_job in data_list:
                        normalized = self._normalize_job(raw_job)
                        if normalized and normalized["job_url"]:
                            jobs_by_url[normalized["job_url"]] = normalized
                            page_count += 1

                    logger.info(
                        "[%s] Từ khóa '%s' - Trang %d/%d: thu được %d job (Tổng cộng không trùng: %d)",
                        self.source_name,
                        keyword,
                        page + 1,
                        min(self.max_pages, nb_pages),
                        page_count,
                        len(jobs_by_url),
                    )

                    if page + 1 >= nb_pages:
                        break

                    time.sleep(self.delay_sec)

        return list(jobs_by_url.values())

