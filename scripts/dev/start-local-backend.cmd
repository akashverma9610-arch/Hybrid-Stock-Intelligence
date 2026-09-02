@echo off
setlocal

rem Start the existing FastAPI entry point as the interactive Windows user.
rem It deliberately supplies no provider values and makes no DPAPI overrides.
cd /d "%~dp0\..\.."
set "APP_ENV=local"
set "DATABASE_BACKEND=sqlite"
set "DATABASE_URL=sqlite:///data/nse_stock_manager.db"
set "CORS_ORIGINS=http://localhost:3001,http://127.0.0.1:3001"
set "HSI_LOCAL_OPERATOR_RUNTIME=true"
set "DHAN_LIVE_MARKET_ENABLED=false"

set "PYTHON_EXE=%USERPROFILE%\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe"
if not exist "%PYTHON_EXE%" (
  echo Local project Python runtime was not found:
  echo %PYTHON_EXE%
  echo Open Codex once to restore its bundled runtime, then run this launcher again.
  pause
  exit /b 1
)

echo Starting local NSE Stock Manager backend at http://127.0.0.1:8000
if not exist "data\nse_stock_manager.db" (
  echo HSI_LOCAL_RUNTIME_REQUIRES_PERSISTENT_DATABASE
  exit /b 1
)
echo Press Ctrl+C in this window to stop it.
"%PYTHON_EXE%" -m uvicorn app.api.main:app --host 127.0.0.1 --port 8000

endlocal
