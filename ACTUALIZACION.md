# Actualizar agente
## 1. Compilar el nuevo exe (ya tenés el código corregido):
compilar.bat

## 2. Subir a GitHub como release v2.1.0 y copiar la URL del asset.

## 3. Actualizar la URL en Firebase:

python set_agente_url.py --github TU_USUARIO/TU_REPO v2.1.0

## 4. En la máquina desplegada — reemplazar manualmente el exe:

Via Remote Desktop, TeamViewer, o acceso físico:


sc stop AgenteMonitoreo
:: Copiar el nuevo AgenteBacar.exe reemplazando el viejo
sc start AgenteMonitoreo

## 5. Verificar que levantó con la nueva versión:


python verificar_actualizaciones.py
Deberías ver version_agente: 2.1.0.