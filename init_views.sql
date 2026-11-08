-- ====================================================================
-- BỘ VIEW PHÂN TÍCH THỊ TRƯỜNG TUYỂN DỤNG IT (JOB MARKET INTELLIGENCE)
-- ====================================================================

-- 1. Bảng xếp hạng Top kỹ năng công nghệ được tuyển nhiều nhất kèm mức lương trung bình
CREATE OR REPLACE VIEW v_top_it_skills AS
SELECT 
    TRIM(jsonb_array_elements_text(skills)) AS skill_name,
    COUNT(*) AS total_openings,
    ROUND(AVG(NULLIF(salary_min, 0)) / 1000000, 1) AS avg_salary_min_tr_vnd,
    ROUND(AVG(NULLIF(salary_max, 0)) / 1000000, 1) AS avg_salary_max_tr_vnd
FROM jobs
WHERE skills IS NOT NULL 
  AND jsonb_array_length(skills) > 0
GROUP BY TRIM(jsonb_array_elements_text(skills))
HAVING COUNT(*) >= 2
ORDER BY total_openings DESC;

-- 2. Phân tích nhu cầu tuyển dụng IT theo khu vực địa lý
CREATE OR REPLACE VIEW v_jobs_by_location AS
SELECT 
    CASE 
        WHEN location ILIKE '%Hồ Chí Minh%' OR location ILIKE '%HCM%' OR location ILIKE '%TP.HCM%' THEN 'TP. Hồ Chí Minh'
        WHEN location ILIKE '%Hà Nội%' OR location ILIKE '%Ha Noi%' THEN 'Hà Nội'
        WHEN location ILIKE '%Đà Nẵng%' OR location ILIKE '%Da Nang%' THEN 'Đà Nẵng'
        WHEN location ILIKE '%Remote%' OR location ILIKE '%Từ xa%' THEN 'Remote / Làm việc từ xa'
        ELSE 'Khác'
    END AS region,
    COUNT(*) AS job_count,
    ROUND(COUNT(*) * 100.0 / SUM(COUNT(*)) OVER (), 1) AS percentage
FROM jobs
WHERE location IS NOT NULL
GROUP BY region
ORDER BY job_count DESC;

-- 3. Top các doanh nghiệp đang tuyển dụng nhiều nhân lực IT nhất
CREATE OR REPLACE VIEW v_top_hiring_companies AS
SELECT 
    company_name,
    COUNT(*) AS total_jobs,
    string_agg(DISTINCT source, ', ') AS platforms,
    MAX(posted_at) AS latest_post
FROM jobs
WHERE company_name IS NOT NULL
GROUP BY company_name
ORDER BY total_jobs DESC;

-- 4. Thống kê thị trường tổng quan theo từng nguồn cào
CREATE OR REPLACE VIEW v_source_breakdown AS
SELECT 
    source,
    COUNT(*) AS total_jobs,
    COUNT(CASE WHEN salary_max IS NOT NULL THEN 1 END) AS jobs_with_salary,
    ROUND(COUNT(CASE WHEN salary_max IS NOT NULL THEN 1 END) * 100.0 / COUNT(*), 1) AS salary_transparency_pct,
    MIN(created_at) AS first_crawled_at,
    MAX(updated_at) AS last_updated_at
FROM jobs
GROUP BY source
ORDER BY total_jobs DESC;

