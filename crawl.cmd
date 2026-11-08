@echo off
set ACTION=%1
set TARGET=%2

if "%ACTION%"=="" set ACTION=stats

if /I "%ACTION%"=="up" (
    echo [INFO] Khoi dong he thong Job Crawl (PostgreSQL + Daily Worker)...
    docker compose up -d --build
    echo [OK] He thong da bat! Xem log bang: crawl logs
    goto :eof
)

if /I "%ACTION%"=="down" (
    echo [INFO] Dang dung toan bo container...
    docker compose down
    goto :eof
)

if /I "%ACTION%"=="logs" (
    echo [INFO] Dang theo doi log...
    docker compose logs -f crawler
    goto :eof
)

if /I "%ACTION%"=="run" (
    if "%TARGET%"=="" (
        echo [INFO] Dang chay thu thap tat ca cac nguon...
        docker compose run --rm crawler python main.py run
    ) else (
        echo [INFO] Dang chay thu thap nguon %TARGET%...
        docker compose run --rm crawler python main.py run --source %TARGET%
    )
    goto :eof
)

if /I "%ACTION%"=="stats" (
    echo [INFO] Lay thong ke du lieu tu PostgreSQL...
    docker compose run --rm crawler python main.py stats
    goto :eof
)

if /I "%ACTION%"=="export" (
    set FMT=%TARGET%
    if "%FMT%"=="" set FMT=csv
    echo [INFO] Dang xuat du lieu ra jobs_export.%FMT%...
    docker compose run --rm crawler python main.py export --format %FMT% --output jobs_export.%FMT%
    goto :eof
)

echo Cac lenh kha dung:
echo   crawl up                : Bat PostgreSQL + API + Scheduler
echo   crawl down              : Tat he thong
echo   crawl logs              : Xem log truc tiep
echo   crawl run vietnamworks  : Thu thap tu VietnamWorks
echo   crawl run topdev        : Thu thap tu TopDev
echo   crawl run itviec        : Thu thap tu ITviec
echo   crawl run topcv         : Thu thap tu TopCV
echo   crawl run               : Chay thu thap ca 4 nguon
echo   crawl stats             : Xem tong so viec lam
echo   crawl export [csv|json] : Xuat du lieu ra file

