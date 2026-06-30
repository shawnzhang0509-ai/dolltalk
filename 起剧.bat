@echo off
chcp 65001 >nul
cd /d "%~dp0"

echo ========================================
echo   DollWorldwide 一键起剧
echo ========================================
echo.

python drama_builder.py dramas\nova_auckland_night.yaml
if errorlevel 1 (
    echo.
    echo 出错了。请确认已安装: pip install -r requirements.txt
    pause
    exit /b 1
)

echo.
echo 完成。输出帧在 output_scenes 文件夹
pause
