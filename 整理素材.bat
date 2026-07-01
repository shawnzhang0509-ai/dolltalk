@echo off
chcp 65001 >nul
cd /d "%~dp0"
echo 把图片按规则命名后放进 inbox 文件夹
echo 命名规则: python sort_assets.py --list-rules
echo.
python sort_assets.py
pause
