# Actualizar agente
## 1. Compilar el nuevo exe (ya tenés el código corregido):
compilar.bat

## 2. Subir el exe a tu servidor (Firebase Storage, etc.) y tener la URL del .exe.

## 3. Actualizar la URL en Firebase:

python set_agente_url.py "https://tu-url/AgenteBacar.exe"

## 4. En la máquina desplegada — reemplazar manualmente el exe:

Via Remote Desktop, TeamViewer, o acceso físico:


sc stop AgenteMonitoreo
:: Copiar el nuevo AgenteBacar.exe reemplazando el viejo
sc start AgenteMonitoreo

## 5. Verificar que levantó con la nueva versión

Lee **`version_agente`** y el último comando en cada PC desde Firestore (no hace falta RDP en cada máquina).

**Desde CMD** (en la carpeta del proyecto, con Python en PATH y `auth/serviceAccountKey.json`):

```bat
verificar_version.bat
```

Equivalente:

```bat
python verificar_actualizaciones.py
```

**Solo una PC** (el hostname contiene el texto, sin distinguir mayúsculas):

```bat
verificar_version.bat --host OFICINA01
```

**Salida JSON** (para otro script):

```bat
verificar_version.bat --json
```

Deberías ver `version_agente` alineado con la versión que desplegaste (por ejemplo `2.1.0` si ese era el build). Si mandaste `ACTUALIZAR_AGENTE`, revisá también el último comando (`ACTUALIZACION_PROGRAMADA`, `ACTUALIZAR_AGENTE_ERROR`, etc.).