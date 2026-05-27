@echo off
echo Iniciando AgenteBacar en modo DEV apuntando al emulador...
echo Asegurate de que el emulador este corriendo: firebase emulators:start --only firestore

set FIRESTORE_EMULATOR_HOST=127.0.0.1:8080

echo FIRESTORE_EMULATOR_HOST=%FIRESTORE_EMULATOR_HOST%
echo.

dist\AgenteBacar.exe --dev
pause
