# Consideraciones de Optimización - Agente de Monitoreo

Este documento recoge las oportunidades de optimización identificadas en el código base,
organizadas por prioridad e impacto.

---

## 1. Bug activo: `.replace` sin efecto (`scanner.py`, línea 405)

```python
nombre_sin_exe = app['nombre'].replace('.exe', '.exe')
```

Esta línea reemplaza `.exe` por `.exe`, es decir, no hace nada.
Probablemente la intención era:

```python
nombre_sin_exe = app['nombre'].replace('.exe', '')
```

**Impacto:** El cruce de datos de CPU contra las aplicaciones activas nunca funciona
correctamente porque la clave de búsqueda no coincide.

---

## 2. Llamada duplicada a `obtener_resoluciones_monitores()` (`perifericos.py`, líneas 82-86)

```python
if not monitores:
    monitores.append({
        'nombre': 'Monitor detectado',
        'resolucion': obtener_resoluciones_monitores()[0] if obtener_resoluciones_monitores() else 'Desconocida'
    })
```

`obtener_resoluciones_monitores()` ejecuta un proceso PowerShell completo (~1-2 seg).
Aquí se llama **dos veces** (una para el `if` y otra para el valor). Debe almacenarse
en una variable:

```python
if not monitores:
    resoluciones = obtener_resoluciones_monitores()
    monitores.append({
        'nombre': 'Monitor detectado',
        'resolucion': resoluciones[0] if resoluciones else 'Desconocida'
    })
```

---

## 3. `except:` sin tipo (bare except) — múltiples archivos

Hay clausulas `except:` sin tipo de excepción en:

| Archivo             | Líneas aproximadas          |
|---------------------|-----------------------------|
| `main.py`           | 29, 48, 127                 |
| `scanner.py`        | 84, 184, 388, 389, 398, 425|
| `firebase_client.py`| 13, 21                      |

Problemas:
- Capturan `KeyboardInterrupt` y `SystemExit`, impidiendo cerrar el proceso limpiamente.
- Ocultan errores reales, dificultando el debugging.

**Recomendación:** Usar `except Exception:` como mínimo, o mejor aún, capturar
excepciones específicas (`OSError`, `subprocess.SubprocessError`, etc.).

---

## 4. Imports dentro de funciones

En `scanner.py`, `obtener_aplicaciones_activas()` importa `json` y `time` dentro del
cuerpo de la función (líneas 314 y 392). Lo mismo ocurre en el fallback (línea 428).

Aunque Python cachea los módulos tras la primera importación, esto añade overhead de
búsqueda en `sys.modules` en cada invocación. Estos imports ya existen o deberían estar
a nivel de módulo.

---

## 5. `subprocess` por cada partición de disco

`obtener_disco_de_particion()` ejecuta un proceso `wmic` para **cada** letra de unidad.
Si el equipo tiene 4 particiones, son 4 procesos nuevos (~400ms cada uno).

**Recomendación:** Obtener el mapeo completo de letra→disco en una sola llamada
y cachearlo, similar a cómo ya se hace con `obtener_modelos_discos_fisicos()`.

```python
def obtener_mapeo_disco_particion():
    """Mapea letras de unidad a número de disco físico (una sola llamada)."""
    mapeo = {}
    try:
        resultado = subprocess.run(
            ['powershell', '-NoProfile', '-Command',
             'Get-Partition | Select-Object DriveLetter, DiskNumber | ConvertTo-Json'],
            capture_output=True, text=True, timeout=10,
            creationflags=subprocess.CREATE_NO_WINDOW
        )
        if resultado.returncode == 0 and resultado.stdout.strip():
            import json
            datos = json.loads(resultado.stdout)
            if isinstance(datos, dict):
                datos = [datos]
            for p in datos:
                letra = p.get('DriveLetter')
                disco = p.get('DiskNumber')
                if letra:
                    mapeo[f"{letra}:"] = str(disco)
    except Exception:
        pass
    return mapeo
```

---

## 6. `wmic` está deprecado

Microsoft deprecó `wmic.exe` a partir de Windows 10 21H1. Se usa en:

- `obtener_modelos_discos_fisicos()` — `wmic diskdrive get`
- `obtener_disco_de_particion()` — `wmic logicaldisk ... assoc`
- `obtener_id_inventario()` — `wmic csproduct get uuid`

**Recomendación:** Migrar a PowerShell con `Get-CimInstance`:

```python
# En lugar de: wmic csproduct get uuid
['powershell', '-NoProfile', '-Command',
 '(Get-CimInstance Win32_ComputerSystemProduct).UUID']

# En lugar de: wmic diskdrive get Index,Model
['powershell', '-NoProfile', '-Command',
 'Get-CimInstance Win32_DiskDrive | Select-Object Index, Model | ConvertTo-Json']
```

---

## 7. Múltiples procesos PowerShell independientes

Cada función de periféricos lanza su propio proceso PowerShell:
- `obtener_monitores()` — 1 proceso
- `obtener_resoluciones_monitores()` — 1 proceso
- `obtener_impresoras()` — 1 proceso
- `obtener_dispositivos_usb()` — 1 proceso
- `obtener_dispositivos_audio()` — 1 proceso
- `obtener_aplicaciones_activas()` — 1 proceso

Cada inicio de `powershell.exe` consume ~200-500ms solo de arranque.

**Recomendación:** Combinar las consultas WMI/CIM en un solo script PowerShell que
retorne un JSON con todas las secciones, o al menos agrupar las que son independientes.
Alternativamente, ejecutar las funciones en paralelo con `concurrent.futures`:

```python
from concurrent.futures import ThreadPoolExecutor, as_completed

def obtener_todos_los_perifericos():
    with ThreadPoolExecutor(max_workers=4) as executor:
        futuros = {
            executor.submit(obtener_monitores): 'monitores',
            executor.submit(obtener_impresoras): 'impresoras',
            executor.submit(obtener_dispositivos_usb): 'dispositivos_usb',
            executor.submit(obtener_dispositivos_audio): 'audio',
        }
        resultado = {}
        for futuro in as_completed(futuros):
            resultado[futuros[futuro]] = futuro.result()
    return resultado
```

---

## 8. Recolección de datos sin paralelismo (`obtener_datos_pc`)

Las funciones dentro de `obtener_datos_pc` se ejecutan secuencialmente. Muchas son
independientes y podrían ejecutarse en paralelo:

- `obtener_ip_publica()` (espera red, ~1-3 seg)
- `obtener_id_anydesk()` (proceso externo, ~1-2 seg)
- `obtener_aplicaciones_activas()` (PowerShell + sleep, ~2-5 seg)
- `obtener_errores_sistema()` (lectura Event Viewer, ~1 seg)
- `obtener_todos_los_perifericos()` (múltiples procesos, ~3-5 seg)

Si se ejecutan en paralelo, el tiempo total baja del acumulado (~10-15 seg)
al de la tarea más lenta (~5 seg).

---

## 9. Caché de IP pública y AnyDesk ID

La IP pública cambia con muy poca frecuencia. `obtener_ip_publica()` hace una
petición HTTP cada vez que se llama. Lo mismo ocurre con `obtener_id_anydesk()`,
que es un valor estático.

**Recomendación:** Cachear estos valores y refrescarlos solo cada N ciclos
(por ejemplo, cada 1 hora):

```python
_cache_ip = {'valor': None, 'timestamp': 0}

def obtener_ip_publica(ttl=3600):
    if time.time() - _cache_ip['timestamp'] < ttl and _cache_ip['valor']:
        return _cache_ip['valor']
    # ... lógica actual ...
    _cache_ip['valor'] = ip
    _cache_ip['timestamp'] = time.time()
    return ip
```

---

## 10. `_es_dispositivo_excluido` reconstruye la lista normalizada cada llamada

En `perifericos.py`, cada vez que se llama `_es_dispositivo_excluido()`, se normaliza
la lista completa `_EXCLUIR_USB`:

```python
exclusiones_norm = [_normalizar_para_comparacion(term) for term in _EXCLUIR_USB]
```

Esto se ejecuta por cada dispositivo USB encontrado.

**Recomendación:** Pre-calcular las exclusiones normalizadas una sola vez a nivel de módulo:

```python
_EXCLUIR_USB_NORM = [_normalizar_para_comparacion(term) for term in _EXCLUIR_USB]

def _es_dispositivo_excluido(nombre: str) -> bool:
    nombre_norm = _normalizar_para_comparacion(nombre)
    return any(term in nombre_norm for term in _EXCLUIR_USB_NORM)
```

---

## 11. `gc.collect()` al final de `obtener_datos_pc`

La llamada explícita a `gc.collect()` al final de `obtener_datos_pc()` rara vez es
necesaria. El recolector de basura de Python gestiona la memoria automáticamente.
Llamar `gc.collect()` fuerza un ciclo completo de recolección que puede pausar
la ejecución ~10-50ms sin beneficio real, ya que los objetos temporales ya han
salido de scope.

**Recomendación:** Eliminar `gc.collect()` a menos que se observe un problema
concreto de memoria (memory leak).

---

## 12. `psutil.cpu_percent(interval=0.5)` es bloqueante

La llamada `psutil.cpu_percent(interval=0.5)` bloquea el hilo durante 500ms para
medir el uso de CPU. Esto se podría evitar con una medición no bloqueante usando
dos llamadas espaciadas:

```python
psutil.cpu_percent(interval=None)  # Primera lectura (no bloquea, retorna 0.0)
# ... hacer otras cosas ...
cpu = psutil.cpu_percent(interval=None)  # Segunda lectura (valor real)
```

---

## 13. File handles sin cerrar (`main.py`, líneas 11-12)

```python
sys.stdout = open(os.devnull, 'w')
sys.stderr = open(os.devnull, 'w')
```

Estos file handles nunca se cierran. Aunque en la práctica el SO los libera
al terminar el proceso, es mejor práctica usar un enfoque que no pierda
la referencia:

```python
_devnull = open(os.devnull, 'w')
sys.stdout = _devnull
sys.stderr = _devnull
```

---

## 14. `shell=True` en subprocess — riesgo de seguridad y rendimiento

Se usa `shell=True` en varias llamadas:
- `servicio_esta_instalado()` — `sc query`
- `instalar_servicio_automaticamente()` — `sc create`, `sc start`, etc.
- `obtener_id_inventario()` — `wmic csproduct get uuid`

`shell=True` añade overhead al crear un proceso `cmd.exe` intermediario y
abre la puerta a inyección de comandos si algún parámetro proviene del usuario.

**Recomendación:** Pasar los comandos como listas sin `shell=True`:

```python
subprocess.run(['sc', 'query', 'AgenteMonitoreo'],
               capture_output=True, text=True, timeout=5,
               creationflags=subprocess.CREATE_NO_WINDOW)
```

---

## 15. `log_debug` abre y cierra el archivo en cada llamada

En `firebase_client.py`, `log_debug()` abre, escribe y cierra el archivo en cada
invocación. En ciclos de alta actividad, esto genera I/O innecesario.

**Recomendación:** Usar el módulo `logging` de Python con `RotatingFileHandler`:

```python
import logging
from logging.handlers import RotatingFileHandler

logger = logging.getLogger('agente')
handler = RotatingFileHandler(
    'C:\\agente_debug.txt', maxBytes=1_000_000, backupCount=2
)
handler.setFormatter(logging.Formatter('%(asctime)s: [Firebase] %(message)s'))
logger.addHandler(handler)
logger.setLevel(logging.DEBUG)

def log_debug(mensaje):
    logger.debug(mensaje)
```

Beneficios adicionales: rotación automática de logs, no crece infinitamente.

---

## 16. Sin reintentos ni backoff en la conexión Firebase

Si Firebase falla temporalmente (red, timeout), la escritura se pierde
silenciosamente. No hay mecanismo de reintento.

**Recomendación:** Implementar reintentos con backoff exponencial para las
operaciones de escritura:

```python
import time

def enviar_con_reintento(ref, datos, intentos=3, base_delay=2):
    for i in range(intentos):
        try:
            ref.set(datos)
            return True
        except Exception as e:
            if i < intentos - 1:
                time.sleep(base_delay * (2 ** i))
            else:
                log_debug(f"Fallo definitivo tras {intentos} intentos: {e}")
    return False
```

---

## 17. `obtener_id_inventario` es inconsistente

Esta función usa `subprocess.check_output` con `shell=True`, mientras que el
resto del código usa `subprocess.run`. Además, no tiene `timeout` ni
`creationflags=CREATE_NO_WINDOW`, por lo que puede mostrar una ventana de
consola fugaz al usuario.

**Recomendación:** Unificar con el patrón del resto del código y cachear
el UUID (nunca cambia):

```python
_uuid_cache = None

def obtener_id_inventario():
    global _uuid_cache
    if _uuid_cache:
        return _uuid_cache
    try:
        resultado = subprocess.run(
            ['powershell', '-NoProfile', '-Command',
             '(Get-CimInstance Win32_ComputerSystemProduct).UUID'],
            capture_output=True, text=True, timeout=10,
            creationflags=subprocess.CREATE_NO_WINDOW
        )
        _uuid_cache = resultado.stdout.strip()
        return _uuid_cache
    except Exception as e:
        return platform.node()
```

---

## Resumen de impacto estimado

| Optimización                         | Tipo         | Impacto en tiempo |
|--------------------------------------|--------------|-------------------|
| Paralelizar recolección de datos     | Rendimiento  | -5 a -10 seg      |
| Cachear disco→partición en 1 llamada | Rendimiento  | -1 a -2 seg       |
| Consolidar procesos PowerShell       | Rendimiento  | -1 a -3 seg       |
| Cachear IP pública y AnyDesk ID      | Rendimiento  | -2 a -4 seg       |
| Fix `.replace('.exe', '.exe')`       | Bug          | Correctitud       |
| Fix doble llamada resoluciones       | Rendimiento  | -1 a -2 seg       |
| Eliminar bare `except:`              | Fiabilidad   | Mejor debugging   |
| Migrar de `wmic` a CIM              | Compatibilidad| Futuro asegurado  |
| Reintentos en Firebase               | Fiabilidad   | Menos datos perdidos|
| Usar módulo `logging`                | Mantenimiento| Logs controlados   |
