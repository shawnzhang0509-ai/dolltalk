@echo off
chcp 65001 >nul
cd /d "%~dp0"
echo 同步 assets/dolls 和 assets/backgrounds 到 config
echo.
python sort_assets.py --sync-only
echo.
pause
