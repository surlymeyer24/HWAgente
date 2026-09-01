# HWAgente

Agente de monitoreo IT para Windows. Se instala como servicio del sistema, recopila información de hardware y software, y la sincroniza con Firebase Firestore en tiempo real. Soporta comandos remotos y auto-actualización.

---

## Funcionalidades

### Servicio Windows

- Se instala automáticamente como servicio (`AgenteMonitoreo`) al ejecutar el `.exe` con doble clic
- Solicita permisos de administrador si es necesario
- Arranque automático con el sistema (`sc create ... start= auto`)
- Modo invisible en producción (sin ventana de consola)

### Datos recopilados

#### Datos estáticos (una vez al inicio)
- Hostname, sistema operativo y arquitectura
- **Versión detallada de Windows** (`windows_version_detallada`: `display_version` como `23H2`, `build`, `ubr`, `edicion`, `build_lab`) leída del registro `HKLM\SOFTWARE\Microsoft\Windows NT\CurrentVersion`
- Modelo de procesador y cantidad de núcleos físicos
- RAM total (GB), módulos por ranura (`modulos_ram`: ocupado, slot, locator, canal, fabricante, modelo/PN, capacidad, velocidad, tecnología DDR, form factor, pines inferidos, voltaje, serial — vacío/`00000000` → `N/A`) y resumen de placa (`ram_placa`: slots totales/ocupados, `canal_modo` single/dual, `max_capacidad_gb`)
- Modelos de discos físicos
- **Tipo de equipo**: Detección basada en el tipo de chasis y presencia de batería (con corrección para Mini PCs que reportan erróneamente chasis de laptop).
#### Datos dinámicos — cada 5 minutos
| Dato | Detalle |
|------|---------|
| CPU | Uso porcentual (muestreo de 0.5s) |
| RAM | Uso porcentual |
| Discos | Espacio total/usado/libre por partición |
| Red | Adaptadores activos, IPs, velocidad, tráfico acumulado; **perfil de conexión** por interfaz (`perfil_red`, `categoria_red` vía `Get-NetConnectionProfile`); **SSID Wi‑Fi** (`wifi_ssid` vía `netsh wlan`) cuando está asociado |
| Servicios críticos | Windows Defender, Windows Update, Firewall, Security Center |

#### Datos pesados — cada 15-60 minutos
| Dato | Frecuencia |
|------|-----------|
| Aplicaciones activas (top 10 por RAM) | 15 min |
| Errores recientes del sistema (Event Viewer) | 30 min |
| Periféricos conectados | 30 min |
| Windows Updates pendientes e historial | 30 min |
| Software crítico (browsers, Office, antivirus) | 60 min |
| Programas instalados (registro Windows, subcolección `computadoras/{uuid}/programas`) | 60 min |
| IP pública y AnyDesk ID | Solo en primera sync |

### Detección de periféricos

- **Monitores**: nombre, resolución, tamaño físico en cm y pulgadas, número de serie y fabricante (vía EDID/WmiMonitorID)
- **Teclado y mouse**: detectados desde dispositivos USB HID, con marca si está disponible; campo `conexion` en Firestore (`usb`, `inalambrico_usb`, `bluetooth`) cuando se puede inferir (nombre del dongle, **PID USB de receptores Logitech** alineado con Solaar/Unifying-Bolt-Lightspeed, o Bluetooth); también se persisten `vid` y `pid` (hex, p. ej. `046D` / `C52B`) cuando el InstanceId PnP los expone y hay un único dispositivo de ese tipo
- **Otros USB**: almacenamiento, cámaras, adaptadores Bluetooth, impresoras USB, etc.
- **Audio**: dispositivos de salida (parlantes, auriculares)
- **Impresoras**: tipo (local/red), driver, puerto, estado, impresora predeterminada

### Software crítico detectado
- Navegadores instalados con versión (Chrome, Firefox, Edge, Brave, Opera)
- Microsoft Office (versión, tipo de instalación: Click-to-Run / MSI)
- Antivirus: estado, protección en tiempo real, antigüedad de firmas

### Comandos remotos (vía Firestore)

Los comandos se envían desde el frontend escribiendo en el documento `tareas/{uuid}`:

| Comando | Acción |
|---------|--------|
| `ACTUALIZAR_DATOS` | Fuerza una sync completa inmediata |
| `INSTALAR_UPDATES` | Instala todas las actualizaciones de Windows pendientes |
| `ACTUALIZAR_AGENTE` | Descarga y reemplaza el `.exe` desde la URL configurada en Firestore |
| `RESETEAR_ID` | Borra la caché local del UUID en el Registro y reinicia el servicio para forzar un nuevo ID limpio |

### Auto-actualización

1. El frontend escribe `ACTUALIZAR_AGENTE` en Firestore
2. **AgenteBacar** lee la URL desde **`config/agente_hw.url`**; si no hay, usa **`config/agente.url`** (legacy). Campos opcionales en `agente_hw`: **`version`** (informativo) y **`sha256`** (para validación criptográfica y evitar binarios corruptos o interceptados).
3. Descarga el nuevo `.exe` (validaciones: tamaño > 100 KB y coincidencia estricta de **SHA256** si fue configurado).
4. Crea un script `.bat` inteligente con reintentos (tolera demoras de I/O en discos lentos) que detiene el servicio, reemplaza el archivo y lo reinicia.
5. El batch se ejecuta de forma desatachada y se autoeliminа

### Dónde vive la versión y cómo comprobarla

| Qué | Dónde |
|-----|--------|
| **Versión del build** | `config/config.py` → constante **`VERSION`**. Debe coincidir con lo que querés mostrar en despliegue y en Firebase. |
| **Lo que reporta cada PC** | En Firestore, documento **`computadoras/{uuid}`** → campo **`version_agente`** (la envía el agente en cada sincronización). |
| **Último comando remoto** | **`tareas/{uuid}`** → **`comando`** (útil tras `ACTUALIZAR_AGENTE`: `ACTUALIZACION_PROGRAMADA`, `ACTUALIZAR_AGENTE_ERROR`, etc.). |

**Las PCs donde solo instalaste el `.exe` no necesitan** la carpeta del proyecto, Python ni `verificar_version.bat`. El agente ya sube la versión a Firebase; la consultás **desde cualquier lugar** (navegador o tu PC de administración).

**Opción A — Sin repo (solo navegador):** en [Firebase Console](https://console.firebase.google.com) → Firestore → colección **`computadoras`** → abrí el documento de esa PC (ID = UUID) y mirá el campo **`version_agente`**. Igual podés ver **`tareas`** para el último comando.

**Opción B — Script en tu PC de administración** (donde sí tenés el clon del repo, Python y `auth/serviceAccountKey.json`): ahí corrés el listado de todas las máquinas sin entrar a cada remoto.

| Forma | Ejemplo |
|-------|---------|
| Atajo Windows | `.\verificar_version.bat` (desde la carpeta del repo) |
| Equivalente | `python verificar_actualizaciones.py` |
| Una PC por hostname | `verificar_version.bat --host OFICINA01` |
| Para scripts | `verificar_version.bat --json` |
| Ayuda | `python verificar_actualizaciones.py -h` |

**Importante:** `verificar_version.bat` **no está en el PATH** y **no va en las PCs cliente**; solo en la máquina donde desarrollás o administrás. Si ejecutás desde otra carpeta (por ejemplo `C:\Windows\Temp`), PowerShell no lo encuentra.

---

## Desarrollo y Pruebas Locales

### Emulador de Firebase Firestore

Para pruebas locales sin afectar la base de datos de producción:

1. **Instalar Firebase CLI** (si no lo tenés):
   ```
   npm install -g firebase-tools
   ```

2. **Inicializar emuladores** (en la raíz del proyecto):
   ```
   firebase init emulators
   ```
   Seleccionar Firestore Emulator.

3. **Iniciar emulador**:
   ```
   firebase emulators:start --only firestore
   ```
   El emulador corre en `http://localhost:8080`, UI en `http://localhost:4000`.

4. **Configurar para desarrollo**:
   - En `config/config.py`, setear `USE_FIREBASE_EMULATOR = True` y `DEBUG_MODE = True`.
   - El archivo `.env.development` ya tiene `FIRESTORE_EMULATOR_HOST=127.0.0.1:8080`.

5. **Ejecutar agente**:
   ```
   python main.py
   ```
   Verificar en la UI del emulador que los datos se suban a la colección `computadoras`.

6. **Para producción**: Cambiar `USE_FIREBASE_EMULATOR = False` y `DEBUG_MODE = False` en `config/config.py`.

**Nota:** El emulador usa datos locales y no persiste entre reinicios. Para producción, usa la BD real de Firebase.

```powershell
Set-Location C:\Users\Usr\Documents\MiniAgente
.\verificar_version.bat
```

O sin cambiar de carpeta:

```powershell
& "C:\Users\Usr\Documents\MiniAgente\verificar_version.bat"
```

(Adaptá la ruta si el clon está en otro disco o carpeta.)

El script **une** `computadoras` y `tareas` por UUID. Si **`version_agente`** coincide con el **`VERSION`** del build que desplegaste, esa máquina ya está corriendo esa versión (puede demorar 1–2 minutos tras reinicio del servicio).

**PowerShell:** usá `cd` / `Set-Location` a la carpeta del proyecto. El comando `cd /d` es solo de **cmd.exe**.

**En una PC remota sin acceso a Firebase:** clic derecho en **`AgenteBacar.exe`** → **Propiedades** → **Detalles**. **Versión del archivo** y **Versión del producto** salen de **`config/config.py` → `VERSION`** (recurso de versión de Windows generado en `AgenteBacar.spec` al compilar). También podés usar PowerShell: `(Get-Item .\AgenteBacar.exe).VersionInfo.FileVersion`. Lo más fiable para inventario sigue siendo **`version_agente`** en Firestore.

---

## Sincronización con Firebase

- **Primera sync**: envío completo con `.set()`
- **Syncs posteriores**: actualizaciones incrementales con `.update()`. Utiliza un **sistema de hashing en memoria** (MD5) para comparar datos pesados antes de enviar, evitando escrituras innecesarias en Firestore y ahorrando costos.
- **ID del documento (`computadoras/{id}`)** — Es el resultado de **`resolver_machine_id`**: normalmente el UUID de placa (WMI); si hay colisión con otro equipo en Firestore, un ID alternativo (`hostname_…`). Ese mismo ID se reutiliza en **todos** los ciclos del servicio y en comandos remotos (`ACTUALIZAR_DATOS`, etc.), no el UUID crudo aislado del escaneo.
- **Recuperación ante 404** — Si un `.update()` falla porque el documento no existe (p. ej. borrado en consola o falló el primer `.set()` por red), el agente hace **`.set(..., merge=True)`** para volver a crear el doc sin quedar en error permanente.
- **Colecciones usadas**:
  - `computadoras` — datos de cada PC (ID = UUID de placa o ID alternativo si hubo colisión; ver `resolver_machine_id` en `firebase_client.py`)
  - `computadoras/{uuid}/programas` — subcolección con un doc por programa instalado (ID = slug del nombre + hash corto). Campos: `nombre`, `version`, `publisher`, `fecha_instalacion` (YYYY-MM-DD), `arquitectura` (`x64` / `x86` / `user`), `ultima_vez_visto`. Se refresca cada 60 min; los programas desinstalados se borran en el siguiente sync.
  - `tareas` — comandos remotos por UUID
  - `config/agente_hw` — URL del `.exe` para **ACTUALIZAR_AGENTE** (opcionalmente `version` informativa y `sha256` para seguridad).
  - `config/agente` — espejo opcional de solo `url` (compatibilidad; `set_agente_url` y el workflow lo mantienen al actualizar)
  - `logs_actualizaciones` — historial de comandos y del flujo **ACTUALIZAR_AGENTE**; cada documento tiene `evento`, `detalle` y opcionalmente **`contexto`** (mapa: URL, host, HTTP, bytes, SHA256, rutas, fase del error, etc.). Eventos típicos de actualización: `ACTUALIZAR_AGENTE_RECIBIDO`, `URL_ENCONTRADA`, `ACTUALIZACION_PROGRAMADA`, `DESCARGA_*`, `REEMPLAZO_*`, `CONFIG_AGENTE_SIN_URL`, `ACTUALIZAR_AGENTE_ERROR` (también reflejado en `tareas.resultado_updates` con `fase` y `contexto`).

---

## Dashboard web (`MiniAgente-Front`)

Aplicación **React + TypeScript + Vite** que lee la colección **`computadoras`** (y datos relacionados) en **Firestore** para visualizar el parque sin instalar el agente en la PC de administración.

| Ruta | Contenido |
|------|-----------|
| **`/`** | Resumen (dashboard) |
| **`/inventario`** | Tabla de inventario: **CPU**, **RAM** (por módulo o total), **discos** agrupados por disco físico con tipo **SSD / HDD / desconocido** en la columna de tipo, **periféricos** (monitores, USB, impresoras, audio). Filtros por categoría (chips + desplegable) y búsqueda por texto. |
| **`/computadoras`** | Listado y detalle por equipo (hardware, red, software crítico, periféricos, incl. `conexion` en USB cuando el agente lo envía). |
| **`/tareas`** | Tareas / comandos remotos |

**Configuración:** variables de entorno `VITE_FIREBASE_*` (misma app Firebase que usa el agente). Detalle de rutas, scripts y tipos: **`MiniAgente-Front/README.md`**.

---

## Estructura del proyecto

```
MiniAgente/
├── MiniAgente-Front/            # Dashboard web (Vite + React); ver README dentro de la carpeta
├── main.py                      # Entry point, lógica del servicio Windows
├── verificar_actualizaciones.py # Lista version_agente y último comando por PC (Firebase)
├── verificar_version.bat        # Atajo CMD para el script anterior
├── config/
│   └── config.py                # Versión, rutas, modo debug
├── src/
│   ├── core/
│   │   ├── scanner.py           # Recopilación de datos de hardware/software
│   │   ├── perifericos.py       # Detección de periféricos USB, monitores, audio
│   │   ├── auto_update.py       # Mecanismo de auto-actualización
│   │   ├── windows_updates.py   # Gestión de Windows Updates
│   │   ├── software_critico.py  # Detección de browsers, Office, antivirus
│   │   └── programas_instalados.py  # Listado de programas desde el registro (Uninstall keys)
│   └── database/
│       └── firebase_client.py   # Integración con Firestore, comandos remotos
├── auth/
│   └── serviceAccountKey.json   # Credenciales de Firebase (no incluido en repo)
├── compilar.bat                 # Detiene el servicio (si existe), limpia build/dist, PyInstaller
└── AgenteBacar.spec             # PyInstaller; embebe versión Windows desde config.VERSION
```

---

## Compilación local (PyInstaller)

Antes de compilar, actualizá **`VERSION`** en `config/config.py` si publicás un release nuevo.

**Símbolo del sistema (cmd):**

```bat
cd /d C:\Users\Usr\Documents\MiniAgente
compilar.bat
```

O solo PyInstaller (sin `pause` del batch):

```bat
cd /d C:\Users\Usr\Documents\MiniAgente
pyinstaller AgenteBacar.spec --clean
```

**PowerShell** (no uses `cd /d`; no existe ahí):

```powershell
Set-Location C:\Users\Usr\Documents\MiniAgente
pyinstaller AgenteBacar.spec --clean
```

Salida: **`dist\AgenteBacar.exe`**. Hace falta **PyInstaller** y el resto de dependencias del proyecto instaladas en ese Python. El **.exe** incluye metadatos de versión (Propiedades → Detalles) alineados con **`VERSION`** en `config/config.py`.

**Si en Propiedades del `.exe` ves 1.0.0.0** (o Firebase reporta `1.0.0` sin querer): suele ser un **.exe comprimido con UPX** (el spec usa **`upx=False`** para evitarlo), un build **viejo sin recurso de versión**, o un release de GitHub Actions donde **no indicaste la versión** en el campo del workflow (el job falla si queda vacío; antes un default erróneo podía dejar todo en 1.0.0). Antes de desplegar manualmente, recompilá con el **`VERSION`** correcto en `config/config.py` y comprobá **Detalles** del `dist\AgenteBacar.exe`. En runtime, **`version_agente`** en Firestore toma la **FileVersion del PE** del ejecutable cuando corre empaquetado (coincide con Propiedades).

### Errores `PermissionError` al compilar

Windows bloquea el borrado de **`build\`** o **`dist\AgenteBacar.exe`** si el ejecutable está en uso.

1. Parar el servicio: `sc stop AgenteMonitoreo` y esperar unos segundos.
2. Cerrar procesos del agente: `taskkill /IM AgenteBacar.exe /F`
3. Borrar artefactos viejos y reintentar, por ejemplo en PowerShell:  
   `Remove-Item -Recurse -Force .\build, .\dist -ErrorAction SilentlyContinue`
4. Si sigue fallando: cerrar el IDE que tenga la carpeta abierta, probar consola **como administrador**, o revisar antivirus.

Si el servicio ejecuta el `.exe` **desde `dist\`**, tenés que pararlo **siempre** antes de recompilar en esa ruta.

---

## Build y deploy

El proyecto usa GitHub Actions para compilar y publicar el `.exe`:

```bash
gh workflow run build-and-deploy.yml --field version=v2.5.0
```

El workflow tiene dos jobs:
1. `build-and-deploy` (`windows-latest`): compila con PyInstaller y publica el `.exe` como GitHub Release
2. `update-firestore` (`ubuntu-latest`, **opcional** con input `actualizar_firestore`): escribe `config/agente_hw` (`url` + `version`) y espeja `url` en `config/agente`. Si elegís **no**, cargá la URL con `python set_agente_url.py "https://..."` o a mano en la consola Firebase.

**Secret requerido:** `FIREBASE_SERVICE_ACCOUNT_B64` — el `serviceAccountKey.json` codificado en base64.

```bash
python -c "import base64; print(base64.b64encode(open('auth/serviceAccountKey.json','rb').read()).decode())"
```

---

## Logs locales

| Archivo | Contenido |
|---------|-----------|
| `C:\agente_debug.txt` | Operaciones de Firebase, errores y **logs de arranque/instalación** (prefijo `[ARRANQUE]`) |
| `C:\agente_actualizaciones.jsonl` | Historial de todos los comandos remotos ejecutados (JSON Lines, un evento por línea) |

### Secuencia de logs de arranque en `agente_debug.txt`

Instalación exitosa (doble clic):
```
[ARRANQUE] INSTALACION_INICIADA — exe: C:\...\AgenteBacar.exe
[ARRANQUE] SC_STOP — ...
[ARRANQUE] SC_DELETE — ...
[ARRANQUE] SC_CREATE — returncode: 0 | stdout: [SC] CreateService CORRECTO.
[ARRANQUE] SC_START — returncode: 0 | ...
[ARRANQUE] INSTALACION_EXITOSA
[ARRANQUE] SVCRUN_INICIO — PID: 1234
[ARRANQUE] SVCRUN_FIREBASE_OK — módulos cargados
[ARRANQUE] SVCRUN_RUNNING — servicio activo
[ARRANQUE] SVCRUN_SYNC_INICIAL — uuid: ...
```

Si falla antes de Firebase (credenciales, archivo faltante, etc.):
```
[ARRANQUE] SVCRUN_INICIO — PID: 1234
[ARRANQUE] SVCRUN_ERROR — FileNotFoundError: ...
```

El evento `ARRANQUE_SERVICIO` también queda en Firestore → colección `logs_actualizaciones`.

---

## Requisitos

- Windows 10 / 11
- Python 3.11 (solo para desarrollo)
- Dependencias: `firebase-admin`, `psutil`, `pywin32`, `wmi`, `requests`, `pyinstaller`
