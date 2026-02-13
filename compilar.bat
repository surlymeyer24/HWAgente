@echo off
echo Limpiando build anterior...
rmdir /s /q build 2>nul
rmdir /s /q dist 2>nul

echo Compilando AgenteBacar...
pyinstaller AgenteBacar.spec --clean

if exist dist\AgenteBacar.exe (
    echo Listo! EXE generado en dist\AgenteBacar.exe
) else (
    echo ERROR: No se genero el EXE. Revisa los errores arriba.
)
pause