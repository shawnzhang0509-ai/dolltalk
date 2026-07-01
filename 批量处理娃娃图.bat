@echo off
setlocal enabledelayedexpansion
chcp 65001 >nul
cd /d "%~dp0"
set /p DOLL=娃娃名（如 nova）: 
set /p MODE=模式 [1]只抠图  [2]抠图+标情绪  [3]AI改表情: 

if "%MODE%"=="3" goto expression
if "%MODE%"=="" set MODE=1

python batch_matte.py --doll %DOLL%
if not "%MODE%"=="1" (
    set /p TAG=用 Kimi 自动标情绪？(y/n): 
    if /i "!TAG!"=="y" python batch_emotion.py --doll %DOLL% --tag
)
python sort_assets.py
pause
exit /b 0

:expression
set /p SRC=选一张原图（如 inbox\raw\ref.jpg）: 
python batch_expression.py --doll %DOLL% --source %SRC% --all --matte
python sort_assets.py
pause
