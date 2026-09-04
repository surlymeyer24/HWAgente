# Piloto — Auditoría de hardware (5–10 PCs)

> **Versión agente mínima:** 5.9.0  
> **Inventario:** panel MVP operativo (Fase 3)  
> **Duración sugerida:** 1–2 semanas

---

## Objetivo

Validar en producción controlada que:

1. El agente detecta cambios reales sin falsos positivos masivos.
2. IT ve y gestiona eventos desde inventario.
3. La limpieza TTL y los logs permiten operar sin intervención manual.

---

## Selección de PCs piloto

Elegir **5–10 equipos** variados:

| Tipo | Cantidad | Motivo |
|------|----------|--------|
| Desktop con 1 monitor | 2 | Caso base |
| Desktop con 2+ monitores | 2 | Serial / duplicados |
| Notebook | 2 | RAM soldada + posible dock |
| PC recién instalada (sin snapshot previo) | 1 | Baseline limpio |
| PC que ya tenía agente v5.6–5.8 | 2 | Upgrade de snapshot |

Anotar hostname y UUID en la tabla de seguimiento (Excel o Firestore).

---

## Pre-requisitos

- [ ] Colección `eventos_hardware` creada en Firestore (dev o prod piloto)
- [ ] Índices compuestos desplegados
- [ ] Inventario: lista + detalle + workflow IT
- [ ] Agente **5.9.0** desplegado en PCs piloto (sin esperar parque completo)
- [ ] IT informado: primera semana puede haber ruido en monitores sin serial

---

## Plan por PC

### Día 0 — Instalación / upgrade

1. Instalar o actualizar agente a 5.9.0.
2. Reiniciar servicio `AgenteMonitoreo`.
3. Esperar **1 ciclo (~5 min)**.
4. Verificar en `C:\agente_debug.txt`:
   - `AUDIT_BASELINE` (PC nueva) **o** sin eventos (upgrade con snapshot existente)
5. Confirmar en registro: `HKLM\SOFTWARE\AgenteBacar\hardware_snapshot` existe.

### Día 1–3 — Pruebas activas

| Prueba | Acción | Resultado esperado | Tiempo |
|--------|--------|-------------------|--------|
| T1 | Conectar monitor externo | 1 evento `monitor/agregado` | ~5 min |
| T2 | Desconectar monitor | 1 evento `monitor/removido` | ~5 min |
| T3 | Reiniciar servicio sin cambios | 0 eventos nuevos | ~5 min |
| T4 | (Opcional) Agregar RAM con PC apagada | 1 evento `ram/agregado` tras encender | Tras boot |
| T5 | Reinicio normal post-cambio CPU (simulado: solo verificar log CPU) | 0 eventos si CPU igual | Al arranque |

### Día 4–14 — Observación pasiva

- IT revisa badge de pendientes diariamente.
- Marcar eventos: `autorizado`, `no_autorizado`, `falso_positivo`.
- Registrar falsos positivos con hostname + fingerprint en hoja de seguimiento.

---

## Checklist IT (inventario)

- [ ] Badge muestra contador correcto
- [ ] Lista filtra por PC, componente, estado
- [ ] Detalle muestra `antes` / `despues`
- [ ] PATCH de estado persiste en Firestore
- [ ] Agente **no** sobrescribe `estado_seguimiento` en re-sync
- [ ] Deduplicación ~10 min funciona (opcional: simular reconexión rápida de monitor)

---

## Checklist agente (logs)

Buscar en `C:\agente_debug.txt`:

| Log | Significado |
|-----|-------------|
| `AUDIT_BASELINE` | Primer snapshot OK |
| `AUDIT_EVENTO_EMITIDO` | Evento individual enviado |
| `AUDIT_EMIT_OK` | Batch Firestore OK |
| `AUDIT_EMIT_FAIL` | Firestore falló; snapshot no avanzó |
| `AUDIT_SNAPSHOT_SAVED` | Snapshot local persistido |
| `AUDIT_SNAPSHOT_FAIL` | Error local (revisar permisos registro/ProgramData) |
| `AUDIT_LIMPIEZA_OK` | Purga TTL (1× día por PC activa) |
| `AUDIT_CICLO` | Resumen cambios en ciclo 5 min |
| `AUDIT_CPU_ARRANQUE` | Diff procesador al arranque |

---

## Criterios de éxito del piloto

| Métrica | Objetivo |
|---------|----------|
| Falsos positivos | < 20% de eventos marcados `falso_positivo` |
| Detección monitor | 100% en pruebas T1/T2 |
| Latencia | Evento visible en inventario ≤ 10 min desde cambio |
| Pérdida de eventos | 0 reportados (salvo Firestore offline prolongado) |
| Baseline masivo | 0 miles de eventos día 1 en deploy piloto |

---

## Rollback

Si el piloto genera demasiado ruido:

1. Setear `HARDWARE_AUDIT_ENABLED = False` en `config/config.py` y redeploy.
2. O desinstalar/reinstalar agente anterior (sync normal sigue funcionando).
3. `RESETEAR_ID` borra snapshot y fuerza nuevo baseline.

---

## Escalamiento post-piloto

Tras 1–2 semanas sin bloqueantes:

1. Comunicar a IT resultados del piloto.
2. Deploy gradual por área (10 → 50 → parque completo).
3. Activar notificaciones push (Fase 7 inventario) si se requiere.

---

## Registro de seguimiento (plantilla)

| Fecha | Hostname | UUID | Prueba | Evento Firestore ID | IT revisó | Estado final | Notas |
|-------|----------|------|--------|---------------------|-----------|--------------|-------|
| | | | T1 monitor | | | | |
| | | | T2 monitor | | | | |

---

*Documento operativo. Complementa `PLAN_AUDITORIA_HARDWARE.md`.*
