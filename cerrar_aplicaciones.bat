@echo off
setlocal

cd /d "%~dp0aplicaciones"
powershell -NoProfile -ExecutionPolicy Bypass -File ".\detener_aplicaciones.ps1"

echo.
echo Apps detenidas.
pause
