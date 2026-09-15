# Reporte de código muerto y archivos junk — HWAgente / MiniAgente

Fecha: 2026-09-15  
Alcance: análisis estático del repo con traza desde `main.py` (servicio `AgenteMonitoreo`) y revisión de scripts de operación.

---

## 1) Metodología usada

1. **Trazado de imports desde entrypoint**:
   - `main.py` (rutas de servicio, `--dev`, instalación automática y comando de servicio).
   - Imports diferidos en `SvcDoRun` y en `firebase_client`.
2. **Cruce de referencias**:
   - Búsqueda de funciones/módulos no referenciados en todo el repo.
3. **Clasificación de scripts de raíz y `scripts/`**:
   - `KEEP`: documentados/encadenados en flujo release/ops/dev.
   - `LIKELY`: utilidades ad-hoc o superseded sin evidencia de uso en flujo principal.
4. **Barrido de código comentado/stubs**:
   - Bloques comentados tipo “código viejo”.
   - stubs muertos reales vs `try/except` defensivos.
5. **Inventario de junk trackeado**:
   - logs/dumps/temporales versionados.

**Exclusiones solicitadas**: se ignoró contenido de `__pycache__`, `.pytest_cache`, `build/` y binarios de `dist_build/`.

---

## 2) Trazabilidad runtime (desde `main.py`)

Cadena principal observada:

- `main.py`
  - `config/config.py`
  - `src/database/firebase_client.py`
  - `src/core/scanner.py`
  - `src/core/hardware_audit.py`
  - `src/core/auto_update.py`
- Dependencias transitivas de core:
  - `src/core/perifericos.py`
  - `src/core/windows_updates.py`
  - `src/core/software_critico.py`
  - `src/core/programas_instalados.py`
  - `src/core/session_tracker.py`
  - `src/core/procesador_parser.py`
  - `src/core/hardware_snapshot.py`
  - `src/core/hardware_diff.py`
  - `src/core/hardware_fingerprint.py`
  - `src/core/detectores/*`
  - `src/core/exe_version.py`

Conclusión: **el núcleo `src/core/*` está mayormente cableado al runtime**, con pocos candidatos de código muerto real.

---

## 3) Hallazgos — HIGH (alta confianza)

| Tipo | Path | Evidencia | Motivo |
|---|---|---|---|
| Función no usada | `src/core/scanner.py` → `obtener_modulos_ram()` | No tiene llamadas en repo | Wrapper huérfano; no participa en flujo runtime actual. |
| Función no usada | `src/database/firebase_client.py` → `_url_actualizacion_pendiente()` | Solo aparece su definición | Fallback legacy obsoleto; el flujo actual usa `_info_actualizacion_pendiente()`. |
| Junk trackeado | `_pytest_full.txt` | Log de ejecución pytest | Artefacto temporal de pruebas; no es código ni documentación persistente. |
| Junk trackeado | `pytest_out.txt` | Log de pytest con fallo histórico | Ruido operativo; no aporta al runtime ni a build. |
| Junk trackeado | `pytest_run_log.txt` | Log de pytest | Igual que arriba. |
| Junk trackeado (indeterminado) | `stop` | Archivo texto con `AgenteMonitoreo` | Nombre/uso no documentado; parece marcador temporal fuera de flujo formal. |

---

## 4) Hallazgos — LIKELY (probable no usado o superseded)

### 4.1 Scripts raíz (`*.py` de operaciones)

| Script | Clasificación | Razón |
|---|---|---|
| `ping_agente.py` | LIKELY | No aparece en README/flujo release; utilidad puntual reemplazable por `verificar_actualizaciones.py` + lectura de `tareas`. |
| `limpiar_y_sincronizar.py` | LIKELY | Script destructivo de limpieza de “fantasmas”, no documentado en flujo principal. |
| `generar_claves_ecdsa.py` | LIKELY | Duplicado funcional de `scripts/firmar_release.py genkey` (más completo). |
| `subir_exe_a_firebase.py` | LIKELY | Camino alternativo antiguo; hoy el flujo principal usa GitHub Release + update de Firestore. |
| `firmar_y_subir_update.py` | LIKELY | Solapa con `scripts/firmar_release.py` + `set_agente_url.py`; menor cobertura y trazabilidad. |
| `enviar_resetear_id.py` | LIKELY | Existe comando runtime `RESETEAR_ID`, pero el script no está documentado en README/ACTUALIZACION. |

### 4.2 `scripts/` (dev/QA locales)

| Script | Clasificación | Razón |
|---|---|---|
| `scripts/test_cpu_local.py` | LIKELY | Test manual local (no evidencia de ejecución CI). |
| `scripts/test_hardware_audit_local.py` | LIKELY | Test manual local (sin integración a pipeline). |
| `scripts/test_seguridad.py` | LIKELY | Smoke manual sobre emulador; útil, pero no integrado en CI. |
| `scripts/security_check.py` | LIKELY | Auditoría ad-hoc local; valor alto, pero fuera del runtime. |

### 4.3 Señales menores de “código dormido”

| Elemento | Clasificación | Razón |
|---|---|---|
| `src/core/hardware_audit.py` → `SECCIONES_MONITORES` | LIKELY | Constante definida pero no referenciada en llamadas productivas actuales. |
| `src/core/detectores/__init__.py` | LIKELY | Módulo agregador no importado directamente por runtime. |

---

## 5) Hallazgos — KEEP (mantener)

| Componente | Motivo de KEEP |
|---|---|
| `main.py` + `src/core/*` principales + `src/database/firebase_client.py` + `config/config.py` | Son la cadena runtime del servicio `AgenteMonitoreo`. |
| `set_agente_url.py` | Referenciado en documentación operativa y mensajes de error del agente. |
| `verificar_actualizaciones.py` + `verificar_version.bat` | Flujo explícito de verificación post-deploy. |
| `enviar_actualizar_agente.py` | Script operativo coherente con comando remoto runtime. |
| `dump_firebase.py` + `scripts/importar_al_emulador.py` + `scripts/emulador.py` | Toolchain de emulador y depuración local documentada. |
| `scripts/firmar_release.py` | Flujo de firma/validación más completo y mantenible. |

---

## 6) Código comentado y stubs

- **No se detectaron bloques grandes de código comentado-out** dentro del core productivo.
- No se encontraron marcadores tipo `TODO/FIXME/HACK/XXX`.
- Hay múltiples `except: pass` y `pass`, pero en su mayoría son **guardas defensivas** (entorno Windows/servicio/firewall/WMI/Firestore) y **no** stubs muertos directos.

---

## 7) Junk trackeado (y verificación de casos pedidos)

### Confirmado trackeado

- `_pytest_full.txt`
- `pytest_out.txt`
- `pytest_run_log.txt`
- `stop` (pendiente de aclaración de propósito)

### No encontrado actualmente como trackeado

- `firebase_dump.json`
- `firebase_dump.md`
- `Untitled`
- `firestore-debug.log` (además figura en `.gitignore`)

### Credenciales (manejo seguro)

- Ruta sensible referenciada en código/docs: `auth/serviceAccountKey.json`.
- **Nota de seguridad**: credenciales presentes/referenciadas; mantener fuera del cuerpo del reporte (sin contenido de secretos).

---

## 8) Orden sugerido de limpieza (sin borrar ahora)

1. **Quick wins (bajo riesgo)**  
   - Retirar de control de versiones logs de pytest y definir política (`artifacts/` o CI artifacts).
2. **Código muerto real (muy bajo riesgo)**  
   - Eliminar o deprecar `obtener_modulos_ram()` y `_url_actualizacion_pendiente()`.
3. **Racionalizar scripts raíz legacy**  
   - Consolidar en `scripts/firmar_release.py` + `set_agente_url.py`; marcar legacy como deprecated.
4. **Documentar scripts “de soporte”**  
   - Si `enviar_resetear_id.py`/`limpiar_y_sincronizar.py` siguen vigentes, documentarlos con advertencias.
5. **Cerrar ambigüedades**  
   - Definir propósito de `stop` o retirarlo.

---

## 9) Top 10 (prioridad recomendada)

1. `pytest_out.txt` (junk trackeado)
2. `_pytest_full.txt` (junk trackeado)
3. `pytest_run_log.txt` (junk trackeado)
4. `src/database/firebase_client.py::_url_actualizacion_pendiente` (muerta)
5. `src/core/scanner.py::obtener_modulos_ram` (muerta)
6. `firmar_y_subir_update.py` (probable legacy superseded)
7. `generar_claves_ecdsa.py` (duplicado de flujo más nuevo)
8. `subir_exe_a_firebase.py` (ruta legacy alternativa)
9. `limpiar_y_sincronizar.py` (ad-hoc destructivo no documentado)
10. `stop` (archivo ambiguo)

---

## 10) Cierre

Se cumple la hipótesis inicial: **core runtime mayormente conectado**, con pocos puntos de código muerto real y varios artefactos/scripts periféricos candidatos a limpieza documental/técnica.
