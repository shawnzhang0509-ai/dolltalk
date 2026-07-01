@echo off
chcp 65001 >nul
cd /d "%~dp0"
set /p DOLL=娃娃名（如 nova）: 
python batch_matte.py --doll %DOLL%
echo.
set /p TAG=是否用 Kimi 自动标情绪？(y/n): 
if /i "%TAG%"=="y" python batch_emotion.py --doll %DOLL% --tag
python sort_assets.py
pause
