<#
.SYNOPSIS
    Script tien ich chay he thong Job Crawl qua Docker Compose tren Windows.
#>

param(
    [Parameter(Position = 0)]
    [string]$Action = "stats",

    [Parameter(Position = 1)]
    [string]$Target = ""
)

switch ($Action.ToLower()) {
    "up" {
        Write-Host ">>> Khoi dong he thong Job Crawl (PostgreSQL + Daily Worker)..." -ForegroundColor Cyan
        docker compose up -d --build
        Write-Host ">>> He thong da bat thanh cong! Dung '.\crawl.ps1 logs' de xem hoat dong." -ForegroundColor Green
    }
    "down" {
        Write-Host ">>> Dang dung toan bo container..." -ForegroundColor Yellow
        docker compose down
        Write-Host ">>> Da dung thanh cong." -ForegroundColor Green
    }
    "logs" {
        Write-Host ">>> Dang theo doi log cua worker (nhan Ctrl+C de thoat)..." -ForegroundColor Cyan
        docker compose logs -f crawler
    }
    "run" {
        if (-not $Target) {
            Write-Host ">>> Dang chay thu thap tat ca cac nguon kich hoat trong .env..." -ForegroundColor Cyan
            docker compose run --rm crawler python main.py run
        } else {
            Write-Host ">>> Dang chay thu thap nguon '$Target'..." -ForegroundColor Cyan
            docker compose run --rm crawler python main.py run --source $Target
        }
    }
    "stats" {
        Write-Host ">>> Lay thong ke du lieu tu PostgreSQL..." -ForegroundColor Cyan
        docker compose run --rm crawler python main.py stats
    }
    "export" {
        $fmt = if ($Target) { $Target } else { "csv" }
        $out = "jobs_export.$fmt"
        Write-Host ">>> Dang xuat du lieu ra file $out..." -ForegroundColor Cyan
        docker compose run --rm crawler python main.py export --format $fmt --output $out
    }
    default {
        Write-Host "Cac lenh kha dung:" -ForegroundColor Yellow
        Write-Host "  .\crawl.ps1 up                : Bat PostgreSQL + API + Scheduler"
        Write-Host "  .\crawl.ps1 down              : Tat he thong"
        Write-Host "  .\crawl.ps1 logs              : Xem log truc tiep"
        Write-Host "  .\crawl.ps1 run vietnamworks  : Thu thap tu VietnamWorks"
        Write-Host "  .\crawl.ps1 run topdev        : Thu thap tu TopDev"
        Write-Host "  .\crawl.ps1 run itviec        : Thu thap tu ITviec"
        Write-Host "  .\crawl.ps1 run topcv         : Thu thap tu TopCV"
        Write-Host "  .\crawl.ps1 run               : Chay thu thap ca 4 nguon"
        Write-Host "  .\crawl.ps1 stats             : Xem tong so viec lam"
        Write-Host "  .\crawl.ps1 export [csv|json] : Xuat du lieu ra file"
    }
}