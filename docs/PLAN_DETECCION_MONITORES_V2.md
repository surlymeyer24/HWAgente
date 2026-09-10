# Plan: Deteccion de monitores v2 — "solo alertar lo nuevo"

> **Estado:** Propuesta  
> **Motivo:** Falsos positivos en piloto — monitor apagado desde boton fisico se reporta como `removido`  
> **Alcance:** Solo monitores. RAM, discos y procesador no cambian.  
> **Referencia:** `PLAN_AUDITORIA_HARDWARE.md` §8.6

---

## 1. Problema

### 1.1 Limitacion de hardware (HPD)

Los monitores usan Hot Plug Detect (HPD), una senal electrica en el pin 19 (HDMI) o pin 16 (DisplayPort) que el monitor **des-aserta** tanto al:

- **Apagar el monitor desde el boton fisico** (corta alimentacion al transceiver TMDS)
- **Desconectar el cable**

Windows recibe la misma notificacion PnP en ambos casos: el dispositivo desaparece de `WmiMonitorID`, de `Get-PnpDevice -Class Monitor`, de `EnumDisplayDevices`, etc. No existe API de Windows que distinga un caso del otro.

### 1.2 Escenario real del piloto

Empleados apagan su monitor al terminar la jornada laboral dejando la PC encendida. El agente (ciclo cada 5 min) detecta que el monitor desaparecio del scan WMI y emite un evento `removido`. A la manana siguiente, al encender el monitor, emite `agregado`. Esto genera **2 eventos falsos por dia por monitor**, multiplicados por cada PC del parque.

### 1.3 APIs probadas (todas con el mismo resultado)

| API / Metodo | Resultado monitor apagado vs desconectado |
|---|---|
| `WmiMonitorID` | Identico: desaparece en ambos |
| `Get-PnpDevice -Class Monitor` | Identico: status `Unknown` en ambos |
| `Win32_DesktopMonitor` | Identico: desaparece en ambos |
| `EnumDisplayDevices` | Identico: no listado en ambos |
| `QueryDisplayConfig` | Identico: target no disponible en ambos |
| DDC/CI (VCP 0xD6) | Solo funciona para DPMS sleep del OS, no boton fisico |
| Registry EDID cache | Se mantiene en ambos, no sirve para distinguir |
| `Win32_PnPSignedDriver` | Identico en ambos |
| `WmiMonitorConnectionParams` | No disponible en ambos |
| `SetupAPI devcon status` | Identico en ambos |

**Conclusion:** No existe solucion por software. Hay que cambiar la logica de deteccion.

---

## 2. Estrategia nueva

### Principio

> "Alertar cuando **aparece algo nuevo**, no cuando **desaparece algo conocido**."

### Tipos de evento por monitor

| Evento | Cuando se emite | Latencia |
|---|---|---|
| `agregado` | Fingerprint nuevo que **nunca** estuvo en el snapshot | Inmediato (proximo ciclo 5 min) |
| `removido` | Fingerprint ausente del scan WMI por mas de **N horas** seguidas | Diferido (configurable, default 48h) |
| `modificado` | Fingerprint existente con cambios en campos no-volatiles | Inmediato (proximo ciclo 5 min) |

### Flujo por ciclo (cada 5 min)

```
1. Scan WMI monitores actuales → lista_actual
2. Cargar snapshot anterior → snapshot.monitores[]
3. Para cada monitor en lista_actual:
   a. Si fingerprint NO esta en snapshot → evento "agregado" + agregar al snapshot con ultima_vez_visto = ahora
   b. Si fingerprint SI esta en snapshot:
      - Actualizar ultima_vez_visto = ahora
      - Si campos cambiaron → evento "modificado"
4. Para cada monitor en snapshot que NO esta en lista_actual:
   a. Si ultima_vez_visto + UMBRAL_HORAS < ahora → evento "removido" + quitar del snapshot
   b. Si no llego al umbral → no hacer nada (puede estar apagado)
5. Guardar snapshot
```

### Beneficios

- **Cero falsos positivos** por apagar/encender monitor a diario
- **Deteccion inmediata** de monitor nuevo (el caso real de auditoria: alguien agrega hardware no autorizado)
- **Deteccion eventual** de monitor genuinamente retirado (48h sin aparecer)
- RAM, discos y CPU no se tocan

---

## 3. Cambios al snapshot

### Formato actual de un monitor en el snapshot

```json
{
  "fingerprint": "SN:ABC123",
  "fabricante": "Dell",
  "nombre": "DELL P2419H",
  "pulgadas": 24,
  "resolucion": "1920x1080",
  "numero_serie": "ABC123",
  "instance_name": "DISPLAY\\DEL..."
}
```

### Formato nuevo (campo agregado)

```json
{
  "fingerprint": "SN:ABC123",
  "fabricante": "Dell",
  "nombre": "DELL P2419H",
  "pulgadas": 24,
  "resolucion": "1920x1080",
  "numero_serie": "ABC123",
  "instance_name": "DISPLAY\\DEL...",
  "ultima_vez_visto": "2026-09-09T14:30:00Z"
}
```

- `ultima_vez_visto`: timestamp ISO8601 UTC. Se actualiza cada ciclo si el monitor esta activo.
- Monitores que estaban en el snapshot sin este campo (upgrade de v1): se les asigna `actualizado_en` del snapshot como valor inicial en la primera carga.

### Migracion de snapshots existentes

Al cargar un snapshot que no tiene `ultima_vez_visto` en sus monitores, el agente les asigna el `actualizado_en` del snapshot como fallback. No se requiere borrar snapshots ni forzar nuevo baseline.

---

## 4. Configuracion

Nuevo parametro en `config/config.py`:

```python
HARDWARE_MONITOR_AUSENCIA_HORAS = int(os.environ.get("HARDWARE_MONITOR_AUSENCIA_HORAS", "48"))
```

- **Default: 48 horas** (2 dias laborales completos)
- Configurable via variable de entorno o futuro remote config
- Solo aplica a monitores; RAM/discos/CPU siguen con deteccion inmediata

---

## 5. Cambios por archivo

### 5.1 `src/core/detectores/monitor_detector.py`

**Actual:**
```python
def detectar_cambios_monitores(anteriores: list, actuales: list) -> list[CambioHardware]:
    return diff_listas("monitor", anteriores, actuales)
```

**Nuevo:** Reemplazar con logica propia que:
1. Reciba `anteriores`, `actuales`, y `umbral_horas` (default de config)
2. Detecte `agregado` inmediato (fingerprint nuevo)
3. Detecte `modificado` inmediato (fingerprint existente con cambios)
4. Detecte `removido` solo si `ultima_vez_visto + umbral < ahora`
5. Retorne `(cambios, monitores_actualizados)` — la lista actualizada de monitores para el snapshot

```python
def detectar_cambios_monitores(
    anteriores: list[dict],
    actuales: list[dict],
    umbral_horas: int = 48,
) -> tuple[list[CambioHardware], list[dict]]:
    """
    Retorna (cambios, monitores_snapshot_actualizado).
    - agregado: inmediato
    - modificado: inmediato
    - removido: solo si ausente > umbral_horas
    """
```

**Importante:** Cambia la firma — retorna una tupla en vez de solo la lista de cambios. Esto permite que el orquestador use la lista actualizada de monitores para el snapshot sin recalcularla.

### 5.2 `src/core/hardware_diff.py`

**Sin cambios en `diff_listas`** — sigue siendo usada por RAM y discos tal cual esta.

Se agrega `ultima_vez_visto` a `_CAMPOS_IGNORAR["monitor"]` para que no dispare un evento `modificado` al actualizar ese timestamp:

```python
_CAMPOS_IGNORAR: dict[str, frozenset[str]] = {
    "monitor": frozenset({"resolucion", "ultima_vez_visto"}),
    ...
}
```

### 5.3 `src/core/hardware_audit.py`

**Cambio en `detectar_cambios`:** La seccion `"monitores"` ya no usa `_DETECTORES_LISTA` generico. Llama a la nueva firma de `detectar_cambios_monitores` y guarda la lista actualizada de monitores para el snapshot.

**Cambio en `procesar_auditoria_hardware`:** Antes de guardar el snapshot final, reemplazar la seccion `monitores` con la lista devuelta por el detector (que tiene `ultima_vez_visto` actualizado y monitores eliminados si pasaron el umbral).

Bosquejo del flujo modificado:

```python
# En detectar_cambios o procesar_auditoria_hardware:
if sec == "monitores":
    cambios_mon, monitores_updated = detectar_cambios_monitores(
        snapshot_anterior.get("monitores", []),
        snapshot_actual.get("monitores", []),
        umbral_horas=HARDWARE_MONITOR_AUSENCIA_HORAS,
    )
    cambios.extend(cambios_mon)
    # monitores_updated se usa al armar el snapshot final
```

### 5.4 `src/core/hardware_snapshot.py`

**Sin cambios funcionales.** El campo `ultima_vez_visto` es un campo mas dentro de cada dict de monitor; `guardar()` y `cargar()` lo serializan/deserializan automaticamente.

Solo verificar que `_normalizar_snapshot` no descarte el campo (no lo hace — solo ordena por fingerprint).

### 5.5 `src/core/hardware_fingerprint.py`

**Sin cambios.** El fingerprint de monitor no incluye `ultima_vez_visto`.

### 5.6 `config/config.py`

**Agregar:**
```python
HARDWARE_MONITOR_AUSENCIA_HORAS = int(os.environ.get("HARDWARE_MONITOR_AUSENCIA_HORAS", "48"))
```

---

## 6. RAM, discos y procesador — sin cambios

Estos componentes no tienen el problema de HPD:

- **RAM:** Solo cambia al abrir fisicamente la PC (apagada). No hay falsos positivos por power state.
- **Discos:** Los discos internos no desaparecen del WMI al apagar un monitor. Discos USB si, pero eso es un `removido` legitimo.
- **Procesador:** Se evalua solo al arranque del servicio. No hay ciclo periodico.

Siguen usando `diff_listas` directamente via sus detectores.

---

## 7. Escenarios de prueba

### 7.1 Empleado apaga monitor al irse (caso principal)

| Paso | Hora | Scan WMI | Snapshot | Evento |
|---|---|---|---|---|
| Monitor encendido | 08:00 | `[SN:ABC]` | `[SN:ABC, visto=08:00]` | Ninguno |
| Apaga monitor (boton) | 18:00 | `[]` | `[SN:ABC, visto=08:00]` | **Ninguno** (no paso umbral) |
| Ciclos nocturnos | 18:05-07:55 | `[]` | `[SN:ABC, visto=08:00]` | **Ninguno** (< 48h) |
| Enciende monitor | 08:00+1d | `[SN:ABC]` | `[SN:ABC, visto=08:00+1d]` | **Ninguno** (actualiza visto) |

**Resultado: 0 eventos falsos.**

### 7.2 Monitor genuinamente retirado

| Paso | Hora | Scan WMI | Snapshot | Evento |
|---|---|---|---|---|
| Monitor conectado | Lunes 08:00 | `[SN:ABC]` | `[SN:ABC, visto=Lun 08:00]` | Ninguno |
| Desconectan monitor | Lunes 10:00 | `[]` | `[SN:ABC, visto=Lun 08:00]` | Ninguno |
| 48h sin monitor | Mier 10:05 | `[]` | visto + 48h < ahora | **`removido` SN:ABC** |

**Resultado: 1 evento legítimo despues de 48h.**

### 7.3 Agregan monitor nuevo (caso auditoria)

| Paso | Scan WMI | Snapshot | Evento |
|---|---|---|---|
| Antes | `[SN:ABC]` | `[SN:ABC]` | — |
| Conectan monitor nuevo | `[SN:ABC, SN:XYZ]` | `[SN:ABC]` | **`agregado` SN:XYZ** inmediato |

**Resultado: deteccion inmediata del nuevo hardware.**

### 7.4 Reemplazo de monitor (quitan uno, ponen otro)

| Paso | Hora | Scan WMI | Evento |
|---|---|---|---|
| Quitan SN:ABC, ponen SN:XYZ | 10:00 | `[SN:XYZ]` | **`agregado` SN:XYZ** inmediato |
| 48h despues | +48h | `[SN:XYZ]` | **`removido` SN:ABC** diferido |

**Resultado: IT ve el agregado inmediatamente. El removido llega 48h despues para confirmar.**

### 7.5 Reconexion rapida (< 5 min)

| Paso | Scan WMI | Evento |
|---|---|---|
| Desconectan | `[]` | Ninguno (no paso umbral) |
| Reconectan antes del proximo ciclo | `[SN:ABC]` | Ninguno (actualiza visto) |

**Resultado: 0 eventos.**

### 7.6 Upgrade de agente (snapshot sin `ultima_vez_visto`)

| Paso | Snapshot | Accion |
|---|---|---|
| Primera carga post-upgrade | `[{SN:ABC, sin ultima_vez_visto}]` | Asigna `actualizado_en` del snapshot como fallback |
| Proximo ciclo, monitor activo | — | Actualiza `ultima_vez_visto` normalmente |
| Proximo ciclo, monitor ausente | — | Cuenta desde el fallback asignado |

**Resultado: transicion transparente, sin nuevo baseline.**

---

## 8. Tests unitarios a agregar/modificar

| Test | Que valida |
|---|---|
| `test_monitor_agregado_inmediato` | Fingerprint nuevo → `agregado` inmediato |
| `test_monitor_ausente_bajo_umbral` | Monitor no visible, < 48h → 0 eventos |
| `test_monitor_ausente_sobre_umbral` | Monitor no visible, > 48h → `removido` |
| `test_monitor_modificado_inmediato` | Cambio en campos no-volatiles → `modificado` |
| `test_monitor_vuelve_antes_umbral` | Desaparece y reaparece → 0 eventos, actualiza visto |
| `test_monitor_ultima_vez_visto_en_snapshot` | La lista retornada tiene el campo actualizado |
| `test_migracion_snapshot_sin_campo` | Snapshot v1 sin `ultima_vez_visto` → fallback funciona |
| `test_ultima_vez_visto_no_dispara_modificado` | Actualizar el timestamp no genera evento |

Tests existentes de RAM, discos y procesador: **no se modifican**.

---

## 9. Impacto en inventario (MiniAgente-Inventario)

**Ningun cambio requerido en inventario.** Los eventos que llegan a Firestore siguen el mismo contrato (`tipo_evento: agregado | removido | modificado`). La unica diferencia es:

- `removido` de monitor llega **48h despues** en vez de inmediatamente
- Menor volumen de eventos (menos falsos positivos)
- IT sigue usando el mismo workflow de revision

---

## 10. Riesgos y mitigaciones

| Riesgo | Mitigacion |
|---|---|
| Monitor retirado tarda 48h en reportarse | Aceptable: el `agregado` del reemplazo es inmediato. IT ve el cambio real sin espera. |
| Snapshot crece con monitores "fantasma" | El cleanup a las 48h los elimina. No hay acumulacion. |
| Falso `removido` si PC estuvo apagada 48h+ (finde largo) | El timer se basa en `ultima_vez_visto`, no en clock real. Si la PC estuvo apagada, el agente no corrio, no avanzo el timer. Solo cuenta horas con el agente activo y el monitor ausente. |
| Cambio de firma de `detectar_cambios_monitores` rompe tests | Actualizar tests existentes de monitores para la nueva firma (tupla). |

---

## 11. Orden de implementacion

1. Agregar `HARDWARE_MONITOR_AUSENCIA_HORAS` a `config/config.py`
2. Agregar `"ultima_vez_visto"` a `_CAMPOS_IGNORAR["monitor"]` en `hardware_diff.py`
3. Reescribir `monitor_detector.py` con la nueva logica
4. Modificar `hardware_audit.py` para usar la nueva firma y pasar monitores actualizados al snapshot
5. Agregar/actualizar tests unitarios
6. Test manual: apagar monitor, verificar 0 eventos; conectar monitor nuevo, verificar `agregado`
7. Build y piloto

---

*Ultima actualizacion: Septiembre 2026*
