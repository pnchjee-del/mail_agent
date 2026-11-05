@echo off
cd /d "%~dp0"
echo ==============================================
echo   Google OAuth Re-Authentication
echo ==============================================
python reauth.py
echo.
pause
