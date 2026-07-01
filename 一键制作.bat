@echo off
chcp 65001 >nul
cd /d "%~dp0"

if not exist .env (
    echo 请先复制 .env.example 为 .env 并填入 MOONSHOT_API_KEY
    pause
    exit /b 1
)

echo 可选大纲:
dir /b outlines\*.yaml 2>nul
echo.
set /p OUTLINE=输入大纲文件名（如 nova_rain_reunion.yaml）: 

python make.py --outline outlines\%OUTLINE%
pause
