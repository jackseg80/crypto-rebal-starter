@echo off
echo 🚀 Starting development server
echo ⚡ Auto-reload enabled
echo 🛑 Press CTRL+C to stop
echo.
echo Activating virtual environment...
call .venv\Scripts\activate.bat
echo.
echo Starting FastAPI server on http://localhost:8000
uvicorn api.main:app --reload --port 8000
pause