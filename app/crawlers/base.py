from abc import ABC, abstractmethod
from typing import Any, Optional


def safe_float(val: Any) -> Optional[float]:
    """Chuyển đổi an toàn giá trị bất kỳ sang float hoặc None nếu không hợp lệ."""
    if val is None:
        return None
    try:
        f = float(val)
        return f if f > 0 else None
    except (ValueError, TypeError):
        return None


class BaseJobCrawler(ABC):
    """Lớp cơ sở cho mọi trình thu thập dữ liệu tuyển dụng (VietnamWorks, TopDev, TopCV, ITviec)."""

    source_name: str = "Unknown"

    @abstractmethod
    def crawl(self) -> list[dict[str, Any]]:
        """Thu thập và chuẩn hóa danh sách công việc theo schema chung của bảng `jobs`."""
        raise NotImplementedError

