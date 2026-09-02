@echo off
setlocal EnableExtensions DisableDelayedExpansion

rem One bounded bridge cycle for Task Scheduler. It never supplies credentials.
cd /d "%~dp0\..\.."

set "PYTHON_EXE=%USERPROFILE%\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe"
if not exist "%PYTHON_EXE%" (
  echo HSI bridge Python runtime is not available. 1>&2
  exit /b 1
)

call :require_environment HSI_EXTERNAL_INTELLIGENCE_SUPABASE_URL || exit /b 2
call :require_environment HSI_EXTERNAL_INTELLIGENCE_SUPABASE_SECRET_KEY || exit /b 2
call :require_environment HSI_EXTERNAL_INTELLIGENCE_INGEST_TOKEN || exit /b 2

set "RUNTIME_REPORT_DIR=%CD%\reports\runtime"
if not exist "%RUNTIME_REPORT_DIR%" mkdir "%RUNTIME_REPORT_DIR%" >nul 2>&1
set "LOG_FILE=%RUNTIME_REPORT_DIR%\external_intelligence_bridge.log"
call :rotate_log

set "CYCLE_OUTPUT=%TEMP%\hsi-bridge-cycle-%RANDOM%%RANDOM%.tmp"
"%PYTHON_EXE%" -m app.runtime bridge-external-intelligence-inbox --once > "%CYCLE_OUTPUT%" 2>&1
set "BRIDGE_EXIT_CODE=%ERRORLEVEL%"
set "SUMMARY="
for /f "usebackq delims=" %%L in (`findstr /b /c:"claimed=" "%CYCLE_OUTPUT%"`) do set "SUMMARY=%%L"
del /q "%CYCLE_OUTPUT%" >nul 2>&1

if defined SUMMARY (
  >> "%LOG_FILE%" echo timestamp=%DATE%T%TIME% exit_code=%BRIDGE_EXIT_CODE% %SUMMARY%
) else (
  >> "%LOG_FILE%" echo timestamp=%DATE%T%TIME% exit_code=%BRIDGE_EXIT_CODE% status=BRIDGE_COMMAND_FAILED
)
exit /b %BRIDGE_EXIT_CODE%

:require_environment
if not defined %~1 (
  echo Required environment variable is not configured: %~1 1>&2
  exit /b 1
)
exit /b 0

:rotate_log
if exist "%LOG_FILE%" for %%I in ("%LOG_FILE%") do if %%~zI GEQ 1048576 move /y "%LOG_FILE%" "%LOG_FILE%.1" >nul
exit /b 0
