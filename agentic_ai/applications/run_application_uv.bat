@echo off
setlocal

REM Determine the directory containing this script
set "SCRIPT_DIR=%~dp0"

REM Use an absolute path for the repository root (one level up from applications)
for %%I in ("%SCRIPT_DIR%..") do set "PROJECT_ROOT=%%~fI"

pushd "%SCRIPT_DIR%"

REM Ensure the applications package is importable when using uv run
set "PYTHONPATH=%PROJECT_ROOT%"

REM Verify uv is available
where uv >nul 2>&1
if errorlevel 1 (
    echo uv executable not found. Install uv from https://docs.astral.sh/uv/ and ensure it is on PATH.
    popd
    endlocal
    exit /b 1
)

REM Start the FastAPI backend in a separate window
start "Agentic AI Backend" uv run python backend.py

REM Launch the Streamlit frontend (blocks until closed)
uv run streamlit run frontend.py

popd
endlocal
