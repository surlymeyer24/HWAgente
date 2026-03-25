@echo off
setlocal
cd /d "%~dp0"
python verificar_actualizaciones.py %*
set EXITCODE=%ERRORLEVEL%
endlocal & exit /b %EXITCODE%
