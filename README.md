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
- Modelo de procesador y cantidad de núcleos físicos
- RAM total (GB)
- Modelos de discos físicos

#### Datos dinámicos — cada 5 minutos
| Dato | Detalle |
|------|---------|
| CPU | Uso porcentual (muestreo de 0.5s) |
| RAM | Uso porcentual |
| Discos | Espacio total/usado/libre por partición |
| Red | Adaptadores activos, IPs, velocidad, tráfico acumulado |
| Servicios críticos | Windows Defender, Windows Update, Firewall, Security Center |

#### Datos pesados — cada 15-60 minutos
| Dato | Frecuencia |
|------|-----------|
| Aplicaciones activas (top 10 por RAM) | 15 min |
| Errores recientes del sistema (Event Viewer) | 30 min |
| Periféricos conectados | 30 min |
| Windows Updates pendientes e historial | 30 min |
| Software crítico (browsers, Office, antivirus) | 60 min |
| IP pública y AnyDesk ID | Solo en primera sync |

### Detección de periféricos

- **Monitores**: nombre, resolución, tamaño físico en cm y pulgadas
- **Teclado y mouse**: detectados desde dispositivos USB HID, con marca si está disponible
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

### Auto-actualización

1. El frontend escribe `ACTUALIZAR_AGENTE` en Firestore
2. El agente lee la URL del ejecutable desde `config/agente.url`
3. Descarga el nuevo `.exe` (validación: > 100 KB)
4. Crea un `.bat` que detiene el servicio, reemplaza el archivo y lo reinicia
5. El batch se ejecuta de forma desatachada y se autoeliminа

---

## Sincronización con Firebase

- **Primera sync**: envío completo con `.set()`
- **Syncs posteriores**: actualizaciones incrementales con `.update()`, solo los campos modificados según su frecuencia
- **Colecciones usadas**:
  - `computadoras` — datos de cada PC (ID = UUID del motherboard)
  - `tareas` — comandos remotos por UUID
  - `config/agente` — URL del ejecutable para actualizaciones
  - `logs_actualizaciones` — historial de actualizaciones del agente

---

## Estructura del proyecto

```
MiniAgente/
├── main.py                      # Entry point, lógica del servicio Windows
├── config/
│   └── config.py                # Versión, rutas, modo debug
├── src/
│   ├── core/
│   │   ├── scanner.py           # Recopilación de datos de hardware/software
│   │   ├── perifericos.py       # Detección de periféricos USB, monitores, audio
│   │   ├── auto_update.py       # Mecanismo de auto-actualización
│   │   ├── windows_updates.py   # Gestión de Windows Updates
│   │   └── software_critico.py  # Detección de browsers, Office, antivirus
│   └── database/
│       └── firebase_client.py   # Integración con Firestore, comandos remotos
├── auth/
│   └── serviceAccountKey.json   # Credenciales de Firebase (no incluido en repo)
└── AgenteBacar.spec             # Spec de PyInstaller para compilar el .exe
```

---

## Build y deploy

El proyecto usa GitHub Actions para compilar y publicar el `.exe`:

```bash
gh workflow run build-and-deploy.yml --field version=v2.5.0
```

El workflow:
1. Compila con PyInstaller en `windows-latest`
2. Publica el `.exe` como GitHub Release
3. Actualiza la URL en Firestore (`config/agente.url`) para que los agentes existentes puedan auto-actualizarse

**Secret requerido:** `FIREBASE_SERVICE_ACCOUNT_B64` — el `serviceAccountKey.json` codificado en base64.

```bash
python -c "import base64; print(base64.b64encode(open('auth/serviceAccountKey.json','rb').read()).decode())"
```

---

## Logs locales

| Archivo | Contenido |
|---------|-----------|
| `C:\agente_debug.txt` | Operaciones de Firebase y errores |
| `C:\agente_actualizaciones.jsonl` | Historial de actualizaciones (JSON Lines) |

---

## Requisitos

- Windows 10 / 11
- Python 3.11 (solo para desarrollo)
- Dependencias: `firebase-admin`, `psutil`, `pywin32`, `wmi`, `requests`, `pyinstaller`
