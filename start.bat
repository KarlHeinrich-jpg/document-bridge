@echo off
setlocal
cd /d "%~dp0"

where py >nul 2>nul
if %errorlevel% equ 0 (
  set "PYTHON_CMD=py -3"
) else (
  where python >nul 2>nul
  if errorlevel 1 (
    echo Python was not found. Please install Python 3.10 or newer.
    pause
    exit /b 1
  )
  set "PYTHON_CMD=python"
)

if not exist ".venv\Scripts\python.exe" (
  echo First launch: creating the local environment...
  %PYTHON_CMD% -m venv .venv
  if errorlevel 1 goto :error
)

.venv\Scripts\python.exe -c "import fastapi, multipart, pypandoc, uvicorn" >nul 2>nul
if errorlevel 1 (
  echo First launch: installing the conversion engine and web dependencies...
  .venv\Scripts\python.exe -m pip install -r requirements.txt
  if errorlevel 1 goto :error
)

.venv\Scripts\python.exe -m app.launcher %*
exit /b %errorlevel%

:error
echo.
echo Document Bridge could not start. See the error above.
pause
exit /b 1

