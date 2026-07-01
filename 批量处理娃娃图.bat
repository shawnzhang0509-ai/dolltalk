@echo off
chcp 65001 >nul
cd /d "%~dp0"
set /p DOLL=娃娃名（如 nova）: 
set /p MATTE=原图需要先抠图吗？(y/n): 

if /i "%MATTE%"=="y" (
    echo 请先把原图放进 inbox\raw\
    python batch_matte.py --doll %DOLL%
)
python sort_assets.py
pause
