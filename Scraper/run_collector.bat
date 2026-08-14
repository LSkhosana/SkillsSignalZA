@echo off
setlocal
cd /d "%~dp0"

if not exist ".venv\Scripts\python.exe" (
  echo Creating local Python environment...
  py -m venv .venv
  if errorlevel 1 goto :error
)

echo Checking the Excel dependency...
".venv\Scripts\python.exe" -m pip install -r requirements.txt
if errorlevel 1 goto :error

echo Starting SkillSignalZA Job Post Collector...
".venv\Scripts\python.exe" app.py
goto :end

:error
echo.
echo Setup could not be completed. Confirm that Python is installed, then try again.
pause

:end
endlocal

