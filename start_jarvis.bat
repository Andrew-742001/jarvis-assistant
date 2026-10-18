@echo off
title JARVIS
cd /d "%~dp0"
if not exist ".venv\Scripts\activate.bat" (
    echo Setting up JARVIS for the first time...
    python -m venv .venv
    call .venv\Scripts\activate.bat
    pip install -r requirements-dev.txt
) else (
    call .venv\Scripts\activate.bat
    echo Checking for updates...
    pip install -q -r requirements.txt
)
echo Starting JARVIS... close this window to stop it.
start "" /b cmd /c "timeout /t 4 /nobreak >nul & start "" http://localhost:8501"
streamlit run app.py
pause
