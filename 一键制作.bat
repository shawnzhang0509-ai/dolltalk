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
set /p CHOICE=输入编号 [1]剧本编辑器  [2]直接渲染: 
if "%CHOICE%"=="2" goto render
start "" python script_editor.py
echo 已在剧本编辑器中打开，编辑保存后可用「渲染」按钮
pause
exit /b 0

:render
set /p DRAMA=输入剧集文件名（如 nova_auckland_night.yaml）: 
python drama_builder.py dramas\%DRAMA%
pause
