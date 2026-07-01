@echo off
chcp 65001 >nul
cd /d "%~dp0"

if not exist .env (
    echo 请先配置 .env（需要 REPLICATE_API_TOKEN）
    pause
    exit /b 1
)

set /p DOLL=娃娃名（如 nova）: 
set /p SRC=原图路径（如 inbox\raw\ref.jpg）: 
set /p EMOS=要生成哪些表情（如 happy,sad,waiting 或输入 all）: 

if /i "%EMOS%"=="all" (
    python batch_expression.py --doll %DOLL% --source %SRC% --all --matte
) else (
    python batch_expression.py --doll %DOLL% --source %SRC% --emotions %EMOS% --matte
)

python sort_assets.py
pause
