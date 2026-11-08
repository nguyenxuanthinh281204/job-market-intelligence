# Job Crawl — Hệ thống đào dữ liệu tuyển dụng IT tự động mỗi ngày

Hệ thống thu thập dữ liệu việc làm IT tự động hàng ngày bằng **Python + PostgreSQL + APScheduler**, được thiết kế theo kiến trúc module hóa để dễ dàng mở rộng cho nhiều nguồn tuyển dụng (hiện tại tích hợp sẵn **VietnamWorks**, sẵn sàng mở rộng thêm TopDev, TopCV, ITviec).

---

## 1. Kiến trúc thư mục

```text
job-crawl/
├── app/
│   ├── crawlers/
│   │   ├── base.py            # Lớp trừu tượng BaseJobCrawler cho mọi nguồn
│   │   ├── vietnamworks.py    # Crawler lấy việc làm IT từ API VietnamWorks
│   │   ├── topdev.py          # Crawler lấy việc làm IT từ API TopDev
│   │   ├── topcv.py           # Crawler HTML TopCV (có bộ phát hiện anti-bot)
│   │   └── itviec.py          # Crawler HTML ITviec (có bộ phát hiện anti-bot)
│   ├── config.py              # Đọc cấu hình từ biến môi trường (.env)
│   ├── database.py            # Kết nối SQLAlchemy + PostgreSQL (cổng 5433)
│   ├── models.py              # Bảng `jobs` và `crawl_runs`
│   ├── pipeline.py            # Luồng điều phối crawl & lưu dữ liệu
│   ├── repository.py          # Logic Upsert + Export CSV/JSON
│   └── scheduler.py           # Cron scheduler chạy tự động mỗi ngày
├── .env                       # Cấu hình môi trường thực tế
├── .env.example               # Mẫu cấu hình môi trường
├── crawl.ps1                  # Script tiện ích 1-click cho PowerShell Windows
├── docker-compose.yml         # Khởi chạy PostgreSQL (5433) + Worker
├── Dockerfile                 # Đóng gói container cho crawler
├── main.py                    # CLI điều khiển (run, schedule, stats, export)
└── requirements.txt           # Danh sách thư viện Python
```

---

## 2. Cơ sở dữ liệu (PostgreSQL)

Hệ thống tự động tạo 2 bảng khi chạy:

1. **`jobs`**:
   - Khóa chống trùng lặp: `job_url` (`UNIQUE`) — mỗi ngày khi chạy lại, nếu tin tuyển dụng đã tồn tại thì hệ thống tự động **cập nhật** (`ON CONFLICT DO UPDATE`), nếu chưa có thì **thêm mới**.
   - Các trường chính: `source`, `external_id`, `title`, `company_name`, `company_logo`, `location`, `salary_min`, `salary_max`, `currency`, `salary_text`, `job_url`, `description`, `requirements`, `benefits`, `skills` (`JSONB`), `job_level`, `working_type`, `posted_at`, `expired_at`, `raw_data` (`JSONB`).
2. **`crawl_runs`**:
   - Lưu lịch sử mỗi lần chạy tự động: thời gian bắt đầu/kết thúc, trạng thái (`RUNNING`, `SUCCESS`, `FAILED`), tổng số tin thu thập, số tin thêm mới, số tin cập nhật.

---

## 3. Hướng dẫn sử dụng nhanh trên Windows (PowerShell)

Hệ thống đã có sẵn script [crawl.ps1](file:///d:/project-daily/job-market-intelligence/job-crawl/crawl.ps1) giúp bạn thực hiện mọi thao tác qua Docker mà **không cần cài đặt Python trên Windows**:

```powershell
# 1. Bật toàn bộ hệ thống (PostgreSQL + Daily Worker chạy ngầm theo lịch hàng ngày)
.\crawl.ps1 up

# 2. Xem log hoạt động trực tiếp của worker
.\crawl.ps1 logs

# 3. Chạy thử thu thập dữ liệu ngay lập tức
.\crawl.ps1 run vietnamworks    # Thu thập VietnamWorks (API)
.\crawl.ps1 run topdev          # Thu thập TopDev (API)
.\crawl.ps1 run itviec          # Thu thập ITviec tự động lật trang (Playwright Chromium)
.\crawl.ps1 run topcv           # Thu thập TopCV tự động lật trang (Playwright Chromium)
.\crawl.ps1 run                 # Thu thập toàn bộ cả 4 nguồn

# 4. Xem thống kê số lượng việc làm hiện có trong PostgreSQL
.\crawl.ps1 stats

# 5. Xuất dữ liệu đã thu thập ra file để mở trong Excel / BI
.\crawl.ps1 export csv          # Tạo file jobs_export.csv (chuẩn font tiếng Việt UTF-8 BOM)
.\crawl.ps1 export json         # Tạo file jobs_export.json

# 6. Dừng hệ thống khi không sử dụng
.\crawl.ps1 down
```

---

## 4. Tuyên bố miễn trừ trách nhiệm (Disclaimer)

- Dự án này được xây dựng thuần túy cho **mục đích học tập, nghiên cứu kỹ thuật Data Engineering** và **phân tích thống kê xu hướng kỹ năng công nghệ (Job Market Intelligence)**.
- Công cụ chỉ đọc thông tin tuyển dụng công khai với tốc độ giới hạn có kiểm soát (`REQUEST_DELAY_SEC`), tuân thủ giới hạn truy cập của máy chủ đích và không thu thập bất kỳ dữ liệu cá nhân (PII) nào.
- Dự án không phục vụ mục đích thương mại và không lưu trữ hay phân phối lại kho dữ liệu thuộc bản quyền của bên thứ ba trên kho mã nguồn này.
