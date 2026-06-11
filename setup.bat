@echo off
REM Board Game Rulebook AI Assistant - Quick Start Script

echo.
echo ========================================
echo Board Game Rulebook AI Assistant
echo Quick Start Setup
echo ========================================
echo.

REM Check if Python is installed
python --version >nul 2>&1
if errorlevel 1 (
    echo Error: Python is not installed or not in PATH
    exit /b 1
)

REM Check if Node.js is installed
node --version >nul 2>&1
if errorlevel 1 (
    echo Error: Node.js is not installed or not in PATH
    exit /b 1
)

echo [1/5] Setting up backend...
cd backend
if not exist venv (
    python -m venv venv
)
call venv\Scripts\activate.bat
pip install -r requirements.txt >nul 2>&1
if not exist .env (
    copy .env.example .env
    echo.
    echo IMPORTANT: Edit backend\.env and add your OpenAI API key!
    echo.
)
cd ..

echo [2/5] Setting up frontend...
cd frontend
call npm install >nul 2>&1
cd ..

echo.
echo ========================================
echo Setup Complete!
echo ========================================
echo.
echo To start the application:
echo.
echo Terminal 1 (Backend):
echo   cd backend
echo   venv\Scripts\activate
echo   python main.py
echo.
echo Terminal 2 (Frontend):
echo   cd frontend
echo   npm run dev
echo.
echo Then open http://localhost:3000 in your browser
echo.
echo API Documentation: http://localhost:8000/docs
echo.
