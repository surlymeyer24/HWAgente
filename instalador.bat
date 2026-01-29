@echo off
:: Instalador del Agente de Monitoreo como Servicio de Windows
:: Debe ejecutarse como Administrador

echo ========================================
echo   Agente de Monitoreo - Instalador
echo ========================================
echo.

:: Verificar permisos de administrador
net session >nul 2>&1
if %errorLevel% neq 0 (
    echo ERROR: Este script requiere permisos de Administrador
    echo.
    echo Click derecho en este archivo y selecciona
    echo "Ejecutar como administrador"
    echo.
    pause
    exit /b 1
)

python instalar_servicio.py

pause