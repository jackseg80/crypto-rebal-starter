@echo off
echo 🚀 Starting development server with CTRL+C working
echo ⚡ Version: main_working.py (stable)
echo 🛑 Press CTRL+C to stop
echo.
uvicorn api.main_working:app --reload --port 8000
pause