import argparse
import logging
import sys

from app.database import get_db_session, init_db
from app.pipeline import run_daily_crawl
from app.repository import export_jobs_to_file, get_database_stats
from app.scheduler import start_scheduler


def setup_logging() -> None:
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s | %(levelname)-7s | %(name)s | %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
        handlers=[logging.StreamHandler(sys.stdout)],
    )


def cmd_init_db() -> None:
    init_db()
    logging.info("Đã khởi tạo các bảng trong PostgreSQL thành công.")


def cmd_stats() -> None:
    init_db()
    with get_db_session() as session:
        stats = get_database_stats(session)
        print("\n=== THỐNG KÊ DỮ LIỆU VIỆC LÀM IT ===")
        print(f"Tổng số việc làm đang lưu trữ: {stats['total_jobs']}")
        print("Phân bổ theo nguồn:")
        for source, count in stats["by_source"].items():
            print(f"  - {source}: {count} jobs")

        print("\nLịch sử các lần chạy gần nhất:")
        if not stats["recent_runs"]:
            print("  (Chưa có lịch sử chạy)")
        for run in stats["recent_runs"]:
            started = run.started_at.strftime("%Y-%m-%d %H:%M:%S") if run.started_at else "N/A"
            print(
                f"  - [{started}] {run.source} | Trạng thái: {run.status} | "
                f"Thu thập: {run.total_fetched} | Thêm mới: {run.inserted_count} | "
                f"Cập nhật: {run.updated_count}"
            )
        print("====================================\n")


def cmd_export(output_path: str, export_format: str, source: str | None = None) -> None:
    init_db()
    with get_db_session() as session:
        total = export_jobs_to_file(
            session=session,
            output_path=output_path,
            export_format=export_format,
            source=source,
        )
        print(f"\n[OK] Đã xuất thành công {total} việc làm ra file: {output_path} (định dạng {export_format.upper()})\n")


def cmd_server(host: str = "0.0.0.0", port: int = 8000) -> None:
    import uvicorn
    logging.info("Khởi động FastAPI server trên %s:%d ...", host, port)
    uvicorn.run("app.api:app", host=host, port=port, reload=False)


def main() -> None:
    setup_logging()

    parser = argparse.ArgumentParser(
        description="Hệ thống thu thập dữ liệu việc làm IT tự động mỗi ngày (Job Crawl)."
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    # Lệnh khởi tạo DB
    subparsers.add_parser("init-db", help="Tạo bảng trong PostgreSQL")

    # Lệnh chạy 1 lần ngay lập tức
    run_parser = subparsers.add_parser("run", help="Chạy thu thập dữ liệu 1 lần ngay lập tức")
    run_parser.add_argument(
        "--source",
        type=str,
        default=None,
        help="Lọc theo tên nguồn (ví dụ: vietnamworks)",
    )

    # Lệnh chạy tự động hàng ngày theo lịch
    subparsers.add_parser("schedule", help="Chạy ngầm với bộ lập lịch tự động mỗi ngày (Cron)")

    # Lệnh xem thống kê
    subparsers.add_parser("stats", help="Xem thống kê dữ liệu đã crawl trong PostgreSQL")

    # Lệnh xuất dữ liệu ra file CSV / JSON
    export_parser = subparsers.add_parser("export", help="Xuất dữ liệu việc làm ra file CSV hoặc JSON")
    export_parser.add_argument(
        "--output",
        "-o",
        type=str,
        default="jobs_export.csv",
        help="Đường dẫn file xuất (mặc định: jobs_export.csv)",
    )
    export_parser.add_argument(
        "--format",
        "-f",
        choices=["csv", "json"],
        default="csv",
        help="Định dạng xuất (csv hoặc json)",
    )
    export_parser.add_argument(
        "--source",
        "-s",
        type=str,
        default=None,
        help="Lọc theo nguồn (vietnamworks, topdev, ...)",
    )

    # Lệnh khởi động API server
    server_parser = subparsers.add_parser(
        "server",
        help="Khởi động FastAPI server nhận dữ liệu từ Chrome Extension và xem Swagger Docs",
    )
    server_parser.add_argument("--host", default="0.0.0.0", help="Host lắng nghe (mặc định 0.0.0.0)")
    server_parser.add_argument("--port", type=int, default=8000, help="Cổng lắng nghe (mặc định 8000)")

    args = parser.parse_args()

    if args.command == "init-db":
        cmd_init_db()
    elif args.command == "run":
        run_daily_crawl(source_filter=args.source)
    elif args.command == "schedule":
        start_scheduler()
    elif args.command == "stats":
        cmd_stats()
    elif args.command == "export":
        cmd_export(output_path=args.output, export_format=args.format, source=args.source)
    elif args.command == "server":
        cmd_server(host=args.host, port=args.port)


if __name__ == "__main__":
    main()

