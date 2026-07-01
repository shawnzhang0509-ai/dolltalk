@echo off
chcp 65001 >nul
cd /d "%~dp0"

echo ========================================
echo   DollWorldwide 一键制作（无 AI）
echo ========================================
echo.

python sort_assets.py
echo.

echo 可选剧集:
dir /b dramas\*.yaml 2>nul
echo.
set /p DRAMA=输入剧集文件名（如 nova_auckland_night.yaml）: 

python drama_builder.py dramas\%DRAMA%
pause
