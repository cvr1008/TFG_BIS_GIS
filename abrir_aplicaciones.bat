@echo off
setlocal

cd /d "%~dp0aplicaciones"
powershell -NoProfile -ExecutionPolicy Bypass -File ".\abrir_apps.ps1"

echo.
echo Apps arrancadas. El portal deberia abrirse en http://127.0.0.1:8040/
pause
