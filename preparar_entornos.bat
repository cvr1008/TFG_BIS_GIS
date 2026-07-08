@echo off
setlocal

cd /d "%~dp0aplicaciones"
powershell -NoProfile -ExecutionPolicy Bypass -File ".\preparar_entorno_offline.ps1"

echo.
echo Preparacion terminada. Si no ha salido ningun error, ya puedes ejecutar ABRIR_DEMO_DEFENSA.bat.
pause
