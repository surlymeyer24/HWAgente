@echo off
echo 🧹 Limpiando archivos residuales...
rmdir /s /q build
rmdir /s /q dist
del /f /q *.spec

echo 🏗️  Compilando el nuevo Agente...
pyinstaller --onefile --noconsole --uac-admin --add-data "auth;auth" --add-data "config;config" --hidden-import=win32timezone --name "AgenteMonitoreo" main.py

echo ✅ Proceso terminado. El EXE esta en la carpeta dist.
pause