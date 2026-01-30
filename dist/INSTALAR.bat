@echo off
:: Instalador Automático del Agente de Monitoreo
:: Click derecho -> "Ejecutar como administrador"

title Instalador Agente de Monitoreo

:: Verificar permisos de administrador
net session >nul 2>&1
if %errorLevel% neq 0 (
    color 0C
    echo.
    echo ========================================
    echo   ERROR: Permisos insuficientes
    echo ========================================
    echo.
    echo Este instalador requiere permisos de Administrador.
    echo.
    echo Por favor:
    echo 1. Click derecho en este archivo
    echo 2. Seleccionar "Ejecutar como administrador"
    echo.
    pause
    exit /b 1
)

cls
python instalar_automatico.py

pause