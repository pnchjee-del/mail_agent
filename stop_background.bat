@echo off
cd /d "%~dp0"
echo ==============================================
echo   Stopping AI Gmail Avatar Assistant Service
echo ==============================================
if exist server.pid (
    set /p PID=<server.pid
    echo Terminating server process PID %PID%...
    taskkill /F /PID %PID% 2>nul
    del server.pid 2>nul
)
if exist daemon.pid (
    set /p PID=<daemon.pid
    echo Terminating daemon process PID %PID%...
    taskkill /F /PID %PID% 2>nul
    del daemon.pid 2>nul
)
taskkill /F /IM pythonw.exe 2>nul
echo Service stopped.

