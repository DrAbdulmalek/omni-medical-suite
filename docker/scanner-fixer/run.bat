@echo off
chcp 65001 >nul
REM ============================================================================
REM Scanner Fixer Pro - Docker Runner (Windows)
REM ============================================================================

setlocal enabledelayedexpansion

set "MODE=web"
set "IMAGE_NAME=scanner-fixer-pro"
set "CONTAINER_NAME=scanner-fixer"

REM Parse arguments
:parse
if "%~1"=="" goto :main
if /i "%~1"=="-m" set "MODE=%~2" & shift & shift & goto :parse
if /i "%~1"=="--mode" set "MODE=%~2" & shift & shift & goto :parse
if /i "%~1"=="-t" set "HF_TOKEN=%~2" & shift & shift & goto :parse
if /i "%~1"=="--token" set "HF_TOKEN=%~2" & shift & shift & goto :parse
if /i "%~1"=="-n" set "CONTAINER_NAME=%~2" & shift & shift & goto :parse
if /i "%~1"=="--name" set "CONTAINER_NAME=%~2" & shift & shift & goto :parse
if /i "%~1"=="-b" set "BUILD=1" & shift & goto :parse
if /i "%~1"=="--build" set "BUILD=1" & shift & goto :parse
if /i "%~1"=="-h" goto :help
if /i "%~1"=="--help" goto :help
echo Unknown option: %~1
goto :help

:help
echo Scanner Fixer Pro - Docker Runner
echo.
echo Usage: run.bat [OPTIONS]
echo.
echo Options:
echo   -m, --mode MODE     Run mode: web^|desktop^|build^|shell (default: web)
echo   -t, --token TOKEN   Hugging Face token
echo   -n, --name NAME     Container name (default: scanner-fixer)
echo   -b, --build         Force rebuild image
echo   -h, --help          Show this help
echo.
echo Modes:
echo   web       - Run Gradio web interface (port 7860)
echo   desktop   - Run Tkinter GUI (requires VcXsrv)
echo   build     - Build image only
echo   shell     - Open shell in container
echo.
echo Examples:
echo   run.bat -m web -t hf_xxxxxxxx
echo   run.bat -m desktop
echo   run.bat --build
echo.
exit /b 0

:main
REM Check Docker
where docker >nul 2>&1
if errorlevel 1 (
    echo [ERROR] Docker not found. Please install Docker Desktop.
    pause
    exit /b 1
)

REM Build image if needed
if "%BUILD%"=="1" goto :build
if "%MODE%"=="build" goto :build
docker image inspect %IMAGE_NAME% >nul 2>&1
if errorlevel 1 goto :build
goto :skip_build

:build
echo [1/3] Building Docker image...
docker build -t %IMAGE_NAME% . --target final
if errorlevel 1 (
    echo [ERROR] Build failed!
    pause
    exit /b 1
)
echo [OK] Image built!

:skip_build
REM Stop existing container
docker ps -q -f name=%CONTAINER_NAME% >nul 2>&1
if not errorlevel 1 (
    echo [2/3] Stopping existing container...
    docker stop %CONTAINER_NAME% >nul 2>&1
    docker rm %CONTAINER_NAME% >nul 2>&1
)

REM Run based on mode
if /i "%MODE%"=="web" goto :web
if /i "%MODE%"=="desktop" goto :desktop
if /i "%MODE%"=="shell" goto :shell
echo [ERROR] Unknown mode: %MODE%
goto :help

:web
echo [3/3] Starting Web Mode (Gradio)...
echo Access at: http://localhost:7860
docker run -d ^
    --name %CONTAINER_NAME% ^
    -p 7860:7860 ^
    -e HF_TOKEN=%HF_TOKEN% ^
    -e HF_USERNAME=DrAbdulmalek ^
    -e GRADIO_SERVER_NAME=0.0.0.0 ^
    -e GRADIO_SERVER_PORT=7860 ^
    -v "%CD%/data:/app/data" ^
    -v "%CD%/output:/app/output" ^
    -v "%CD%/local_dataset_backups:/app/local_dataset_backups" ^
    --restart unless-stopped ^
    %IMAGE_NAME% ^
    python gradio_scanner_app.py

echo [OK] Container started!
echo Logs: docker logs -f %CONTAINER_NAME%
pause
exit /b 0

:desktop
echo [3/3] Starting Desktop Mode (Tkinter)...
echo NOTE: Ensure VcXsrv is running with "Disable access control" checked!
echo Download: https://sourceforge.net/projects/vcxsrv/

REM Check if DISPLAY is set
if "%DISPLAY%"=="" (
    echo [WARNING] DISPLAY not set. Using default: host.docker.internal:0.0
    set "DISPLAY=host.docker.internal:0.0"
)

docker run -it --rm ^
    --name %CONTAINER_NAME%-desktop ^
    -e DISPLAY=%DISPLAY% ^
    -e HF_TOKEN=%HF_TOKEN% ^
    -e HF_USERNAME=DrAbdulmalek ^
    -v "%CD%/data:/app/data" ^
    -v "%CD%/output:/app/output" ^
    -v "%CD%/local_dataset_backups:/app/local_dataset_backups" ^
    %IMAGE_NAME% ^
    python desktop_scanner_fixer_pro_v2.py

exit /b 0

:shell
echo [3/3] Opening shell...
docker run -it --rm ^
    --name %CONTAINER_NAME%-shell ^
    -e HF_TOKEN=%HF_TOKEN% ^
    -v "%CD%/data:/app/data" ^
    -v "%CD%/output:/app/output" ^
    %IMAGE_NAME% ^
    /bin/bash
exit /b 0
