@echo off
cd /d "%~dp0"

echo Limpiando build anterior...
rmdir /s /q build 2>nul
rmdir /s /q dist_build 2>nul

echo Compilando AgenteBacar...
pyinstaller AgenteBacar.spec --clean --distpath dist_build

if exist dist_build\AgenteBacar.exe (
    echo Listo! EXE generado en dist_build\AgenteBacar.exe
    echo Ahora podes ejecutar firmar_y_subir_update.py pasando dist_build\AgenteBacar.exe
) else (
    echo ERROR: No se genero el EXE. Revisa los errores arriba.
)
pause