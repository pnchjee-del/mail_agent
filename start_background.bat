@echo off
cd /d "%~dp0"
echo ==============================================
echo   Starting AI Gmail Avatar Assistant Service
echo ==============================================
start "" pythonw server.py
echo.
echo Service started on http://127.0.0.1:5000!
echo Autonomous email scanner is active.
echo Your 3D Avatar will be active directly inside Gmail!
echo.
echo Activity logs: %~dp0agent_activity.log
echo.
timeout /t 3 /nobreak >nul 2>&1
