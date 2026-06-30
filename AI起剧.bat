@echo off
chcp 65001 >nul
cd /d "%~dp0"

echo ========================================
echo   DollWorldwide AI 起剧 (Kimi)
echo ========================================
echo.

if not exist .env (
    echo 请先复制 .env.example 为 .env 并填入 MOONSHOT_API_KEY
    pause
    exit /b 1
)

set /p THEME=输入主题（如 雨夜咖啡馆）: 
python generate_drama.py --provider kimi --doll nova --theme "%THEME%" --build

echo.
pause
