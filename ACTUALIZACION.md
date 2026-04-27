# Actualizar agente

## 1. Compilar el nuevo exe

Subí la versión en **`config/config.py`** (`VERSION = "x.y.z"`) para que las PCs reporten bien en Firebase.

**cmd** (en la carpeta del repo):

```bat
cd /d C:\Users\Usr\Documents\MiniAgente
compilar.bat
```

**PowerShell:**

```powershell
Set-Location C:\Users\Usr\Documents\MiniAgente
pyinstaller AgenteBacar.spec --clean
```

El `.exe` queda en **`dist\AgenteBacar.exe`**.

### Si PyInstaller falla con `PermissionError`

- **`build\...` o `dist\AgenteBacar.exe` acceso denegado:** el agente o el servicio sigue usando esos archivos.
  - `sc stop AgenteMonitoreo`
  - `taskkill /IM AgenteBacar.exe /F`
  - Borrá `build` y `dist` y volvé a compilar (ver sección **Compilación local** en `README.md`).

## 2. Subir el exe a tu servidor (Firebase Storage, etc.) y tener la URL del .exe.

## 3. Actualizar la URL en Firebase (AgenteBacar)

Documento **`config/agente_hw`** (`url` obligatoria; `version` y `sha256` opcionales). Se espeja `url` en **`config/agente`** para compatibilidad.

```bat
python set_agente_url.py "https://tu-url/AgenteBacar.exe"
python set_agente_url.py "https://tu-url/AgenteBacar.exe" "2.4.0"
python set_agente_url.py "https://tu-url/AgenteBacar.exe" "2.4.0" "hash_sha256_del_archivo"
```

Si usás **GitHub Actions**, podés dejar que el job opcional actualice Firestore (`actualizar_firestore: si`) o poner **no** y hacer este paso a mano.

## 4. En la máquina desplegada — reemplazar manualmente el exe:

Via Remote Desktop, TeamViewer, o acceso físico:


sc stop AgenteMonitoreo
:: Copiar el nuevo AgenteBacar.exe reemplazando el viejo
sc start AgenteMonitoreo

## 5. Verificar que levantó con la nueva versión

- **Origen:** el agente envía a Firestore el valor de **`VERSION`** del build → campo **`version_agente`** en **`computadoras/{uuid}`**.
- **Comprobación:** ese valor debe coincidir con el **`VERSION`** de `config/config.py` del release que desplegaste (puede tardar 1–2 min en actualizarse tras el reinicio del servicio).

Las PCs cliente **solo tienen el `.exe`**: no hace falta copiar el repo ni `verificar_version.bat` al remoto. La versión ya está en Firestore.

**Sin instalar nada (cualquier PC con navegador):** Firebase Console → Firestore → **`computadoras`** → documento de la máquina → campo **`version_agente`**. En **`tareas`** ves el último comando.

**Desde tu PC de administración** (sí: carpeta del proyecto, Python y `auth/serviceAccountKey.json`) podés listar todas a la vez. El `.bat` no está en el PATH; ejecutalo desde el repo o con ruta completa.

**cmd:**

```bat
cd /d C:\Users\Usr\Documents\MiniAgente
verificar_version.bat
```

**PowerShell:**

```powershell
Set-Location C:\Users\Usr\Documents\MiniAgente
.\verificar_version.bat
```

Ruta completa sin `cd`: `& "C:\Users\Usr\Documents\MiniAgente\verificar_version.bat"` (entre comillas si hay espacios).

Equivalente con Python (también desde la carpeta del repo):

```bat
python verificar_actualizaciones.py
```

**Solo una PC** (el hostname contiene el texto, sin distinguir mayúsculas):  
`.\verificar_version.bat --host OFICINA01`

**Salida JSON:** `.\verificar_version.bat --json`

Deberías ver `version_agente` alineado con la versión que desplegaste (por ejemplo `2.1.0` si ese era el build). Si mandaste `ACTUALIZAR_AGENTE`, revisá también el último comando (`ACTUALIZACION_PROGRAMADA`, `ACTUALIZAR_AGENTE_ERROR`, etc.).