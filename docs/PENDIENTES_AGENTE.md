# Pendientes — Agente (MiniAgente)

> **Estado código:** Fases 1–6 implementadas (v5.9.0 en `config/config.py`)  
> **Commits:** `feat(auditoria-hardware)` + `fix(ci)` UTF-8  
> **Referencia:** `PLAN_AUDITORIA_HARDWARE.md`

---

## Resumen

El módulo de auditoría de hardware en el agente está **completo en código**. Lo que queda es **despliegue, validación en PCs reales y operación**, no desarrollo de features v1.

| Área | Estado |
|------|--------|
| Infra (snapshot, diff, emit) | Hecho |
| Monitores, RAM, discos | Hecho |
| Procesador (solo arranque) | Hecho |
| Endurecimiento (logs, TTL, errores) | Hecho |
| Tests unitarios (40) | Hecho |
| Compilar / desplegar `.exe` | **Pendiente** |
| Piloto 5–10 PCs | **Pendiente** |

---

## Pendientes operativos (prioridad alta)

### 1. Build y release del `.exe`

- [ ] Ejecutar workflow **Build and Deploy Agente** con versión alineada (ej. `v5.9.0`)
- [ ] Verificar que el paso **Bump version in config.py** pasa (fix UTF-8 ya aplicado)
- [ ] Confirmar release en GitHub con `AgenteBacar.exe`
- [ ] (Opcional) Actualizar `config/agente_hw` en Firestore vía workflow o manual

### 2. Piloto en 5–10 PCs

Seguir **`docs/PILOTO_AUDITORIA_HARDWARE.md`**.

- [ ] Elegir PCs variadas (desktop, notebook, multi-monitor, upgrade desde v5.6–5.8)
- [ ] Instalar / actualizar agente v5.9.0
- [ ] Día 0: verificar `AUDIT_BASELINE` en `C:\agente_debug.txt`
- [ ] Pruebas T1/T2: conectar / desconectar monitor (~5 min)
- [ ] (Opcional) Prueba RAM con PC apagada
- [ ] Registrar falsos positivos y feedback para IT

### 3. Coordinación con inventario

- [ ] Confirmar que inventario lee `eventos_hardware` en el **mismo proyecto** Firebase (dev/prod)
- [ ] Validar contrato de campos del evento (§6.2 del plan)
- [ ] No desplegar parque completo hasta que inventario MVP esté operativo

---

## Pendientes técnicos (prioridad media)

### Firestore (lado agente)

- [ ] **No** hace falta crear la colección vacía: se crea al **primer evento**
- [ ] Índice `(expire_at ASC)` recomendado para la purga TTL del agente (`limpiar_eventos_hardware_viejos`)
  - La purga funciona sin índice en volúmenes chicos; con 200+ PCs conviene crearlo
- [ ] Reglas de seguridad: el agente escribe vía **service account** (Admin SDK), no depende de rules del cliente — coordinar con inventario (§15 del plan)

### Validación manual (no cubierta solo por unit tests)

- [ ] Snapshot persiste en `HKLM\SOFTWARE\AgenteBacar\hardware_snapshot` tras reinicio servicio
- [ ] Fallback a `C:\ProgramData\AgenteBacar\hardware_snapshot.json` en PC con snapshot grande (si aplica)
- [ ] `HARDWARE_AUDIT_ENABLED = False` desactiva audit sin romper sync normal
- [ ] `RESETEAR_ID` borra snapshot y fuerza nuevo baseline
- [ ] Tras corte de red: `AUDIT_EMIT_FAIL` y reintento en próximo ciclo (mismo diff)

### Logs a monitorear en piloto

| Log | Significado |
|-----|-------------|
| `AUDIT_BASELINE` | Primer snapshot OK |
| `AUDIT_EVENTO_EMITIDO` | Evento enviado |
| `AUDIT_EMIT_OK` / `AUDIT_EMIT_FAIL` | Resultado Firestore |
| `AUDIT_SNAPSHOT_SAVED` / `AUDIT_SNAPSHOT_FAIL` | Persistencia local |
| `AUDIT_LIMPIEZA_OK` | Purga TTL (~1× día) |
| `AUDIT_CICLO` | Cambios en ciclo 5 min |
| `AUDIT_CPU_ARRANQUE` | Diff CPU al arranque |

---

## Pendientes opcionales (Fase 7+ — no bloquean v1)

| Ítem | Notas |
|------|-------|
| Debounce monitores | Campo `evento_relacionado`; reduce pares removido+agregado |
| Periféricos USB selectivos | Fuera de alcance v1 |
| Notificaciones push | Solo inventario → `PLAN_NOTIFICACIONES_HARDWARE_INVENTARIO.md` |
| `ACTUALIZAR_DATOS` dispara audit inmediato | No requerido; latencia ~5 min aceptada |
| Actualizar checkboxes en `PLAN_AUDITORIA_HARDWARE.md` | Documentación |

---

## Limitaciones conocidas (documentar a IT, no son bugs)

- Monitores sin serial → posibles falsos positivos o ambigüedad
- Desconectar monitor ~30 s y reconectar → 2 eventos (v1: marcar `falso_positivo`)
- Cambio de CPU solo se detecta al **reiniciar** el servicio / PC
- Upgrade v5.6→v5.9: primer ciclo agrega RAM/discos/CPU al snapshot **sin alertas**

---

## Criterios de “agente listo para producción”

- [ ] `.exe` v5.9.0 publicado
- [ ] Piloto 5–10 PCs sin bloqueantes críticos
- [ ] IT puede ver eventos en inventario y cerrar casos
- [ ] Deploy gradual acordado (piloto → área → parque)

---

*Última actualización: Septiembre 2026 — post Fase 6.*
