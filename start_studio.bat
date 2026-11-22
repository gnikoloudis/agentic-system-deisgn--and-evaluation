@echo off
title HarnessForge - Agent Architecture Design & Evaluation Studio
echo ============================================================================
echo   HarnessForge - Multi-Harness Agent Architecture Design & Evaluation Tool
echo ============================================================================
echo.
echo [1/2] Starting FastAPI Backend Server on http://127.0.0.1:8765 ...
start "HarnessForge Backend API" cmd /k "cd /d "%~dp0backend" && .\.venv\Scripts\harnessforge.exe serve --reload"

timeout /t 2 /nobreak >nul

echo [2/2] Starting React Flow Visual Web Studio on http://localhost:5173 ...
start "HarnessForge Web Studio" cmd /k "cd /d "%~dp0frontend" && npm run dev"

timeout /t 3 /nobreak >nul
echo.
echo Opening http://localhost:5173 in your default browser...
start http://localhost:5173
echo.
echo Done! Keep the two opened terminal windows running while using HarnessForge.
pause
