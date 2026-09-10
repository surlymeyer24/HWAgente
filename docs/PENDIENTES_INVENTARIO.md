# Pendientes — Inventario (MiniAgente-Inventario)

> **Alcance:** Java + React — lectura, UI y workflow IT sobre `eventos_hardware`  
> **El agente no participa** en estos ítems (solo escribe eventos)  
> **Referencia:** `PLAN_AUDITORIA_HARDWARE.md` §9 · Notificaciones push → `PLAN_NOTIFICACIONES_HARDWARE_INVENTARIO.md`  
> **Código:** repo `MiniAgente-Inventario` (`inventario/` backend + `inventario-front/` React)

---

## Resumen

El agente ya emite eventos a Firestore. Inventario debe **consumirlos, mostrarlos y permitir que IT gestione casos**.

| Área | Estado |
|------|--------|
| Fase 3 — MVP (lista, badge, workflow) | **Implementado** (gaps menores abajo) |
| Fase 4 — UI ram / disco / procesador | **Parcial** (iconos/filtro sí; render tipado pendiente) |
| Firestore índices + reglas | **Parcial** (índices básicos sí; reglas escritas, falta deploy) |
| Fase 7 — Notificaciones push | Opcional |
| Piloto con agente v5.9.0 | **Pendiente** (validación operativa) |

*Última revisión contra código: septiembre 2026.*

---

## Fase 3 — MVP (prioridad alta)

### Backend Java

- [x] Modelo `EventoHardware` — mapeo snake_case Firestore (`models/EventoHardware.java`)
- [x] Repository / Service — lectura + update estados (solo campos IT)
- [x] API REST (`/api/eventos-hardware`):
  - [x] `GET ?estado=pendiente&leido=false` (badge + lista)
  - [x] `GET ?uuid={uuid}` (timeline por PC)
  - [x] `GET /{id}` (detalle)
  - [x] `GET /pendientes-count` (contador badge — extra vs plan original)
  - [x] `PATCH /{id}` — body: `estadoSeguimiento`, `leido`, `notasIt`
- [x] **Deduplicación** al listar: mismo `uuid` + `fingerprint` + `tipo_evento` + `tipo_componente` en ventana ~10 min (`EventoHardwareService.deduplicar`)
- [x] El backend **no** crea eventos; solo actualiza campos de workflow
- [ ] **`revisado_por` en PATCH** — el modelo y DTO de lectura lo tienen; el update solo escribe `revisado_en` al cambiar estado, no persiste quién revisó (falta tomar email del usuario autenticado)

### Frontend React

- [x] **Badge** en sidebar — contador `pendiente` + `leido=false` vía `GET /pendientes-count` (`SidebarNav` → “Auditoría HW”)
- [x] **Lista global** `/eventos-hardware` — filtros: estado, componente, búsqueda por PC/UUID/fingerprint
- [ ] **Filtro por fecha** en lista global (no implementado; solo orden por timestamp en backend)
- [x] **Detalle evento** — `antes` / `despues`, notas, botones:
  - [x] Autorizado → `autorizado`
  - [x] No autorizado → `no_autorizado`
  - [x] Falso positivo → `falso_positivo`
  - [x] Tomar en revisión → `en_revision` (extra vs plan original)
- [x] Al abrir evento: `leido=true` automático
- [x] **Timeline** en ficha de computadora (`ComputadoraEventosTimeline` en `ComputadoraDetail`)

### Contrato Firestore — campos del agente (solo lectura)

```json
{
  "uuid": "string",
  "hostname": "string",
  "tipo_componente": "monitor | ram | disco | procesador",
  "tipo_evento": "agregado | removido | modificado",
  "fingerprint": "string",
  "antes": "object | null",
  "despues": "object | null",
  "origen": "agente",
  "version_agente": "string",
  "timestamp": "Timestamp",
  "expire_at": "Timestamp",
  "estado_seguimiento": "pendiente",
  "leido": false
}
```

### Campos que escribe inventario (PATCH)

```json
{
  "estado_seguimiento": "en_revision | autorizado | no_autorizado | falso_positivo",
  "leido": true,
  "revisado_por": "usuario@empresa",
  "revisado_en": "Timestamp",
  "notas_it": "string"
}
```

**Importante:** el agente **no** debe sobrescribir estos campos en re-sync (solo crea docs).

**Gap actual:** `revisado_en` se escribe al resolver; `revisado_por` aún no.

---

## Fase 4 — Ajustes UI (prioridad media)

Tras MVP con monitores, extender para componentes que el agente ya reporta (v5.9.0):

- [x] Labels e iconos para `ram`, `disco`, `procesador` (lista + detalle)
- [ ] Render `antes`/`despues` **por tipo** (hoy es genérico: lista todas las claves del objeto):
  - **RAM:** slot, locator, capacidad_gb, modelo, numero_serie
  - **Disco:** device_id, modelo, tipo, numero_serie
  - **Procesador:** nombre_completo, nucleos_fisicos, gama, modelo
- [x] Filtro por `tipo_componente` en lista global (client-side)
- [ ] Nota UX procesador en detalle: evento llega **tras reinicio** del servicio, no en caliente

---

## Firestore — setup (prioridad alta, paralelo al MVP)

### Colección

- [x] **No** crear colección vacía obligatoriamente (la crea el agente al primer evento)
- [ ] (Opcional) **Doc de prueba** manual para desarrollar UI antes del agente — ver ejemplo en conversación / plan §6.2
- [ ] Confirmar proyecto **dev** vs **prod** alineado con agente

### Índices compuestos

Definidos en `inventario/firestore.indexes.json`. El repository ordena en memoria en queries filtradas para reducir dependencia de índices compuestos.

| Índice | Uso | Estado |
|--------|-----|--------|
| `estado_seguimiento ASC` + `timestamp DESC` | Lista pendientes, badge | [x] En `firestore.indexes.json` |
| `estado_seguimiento ASC` + `leido ASC` | Contador badge (query parcial) | [x] En `firestore.indexes.json` |
| `uuid ASC` + `timestamp DESC` | Timeline por PC | [x] En `firestore.indexes.json` |
| `tipo_componente ASC` + `timestamp DESC` | Filtro por componente (server-side) | [ ] Pendiente (hoy filtro client-side) |
| `expire_at ASC` | Purga / consultas TTL | [ ] Pendiente |

Queries adicionales (ej. `leido + estado_seguimiento + timestamp`) pueden requerir índices extra — crear cuando aparezca el error en dev.

### Reglas de seguridad (borrador plan §15)

```
eventos_hardware:
  - create: false          (solo service account del agente)
  - read: authenticated IT
  - update: authenticated IT (solo campos workflow)
  - delete: admin only
```

- [x] Implementar en dev — bloque `eventos_hardware` en `firestore.rules` (alineado con roles `usuarios/`)
- [ ] Desplegar en dev (`firebase deploy --only firestore:rules`) y probar
- [ ] Desplegar en prod antes del piloto

> **Nota:** el backend Spring y el agente usan Admin SDK (ignoran reglas). Las reglas protegen acceso directo desde cliente Firestore; hoy el front consume solo la API REST.

---

## Piloto con agente (prioridad alta)

Coordinar con **`docs/PILOTO_AUDITORIA_HARDWARE.md`** (lado agente).

### Checklist IT

- [ ] Badge muestra contador correcto
- [ ] Lista filtra por PC, componente, estado
- [ ] Detalle muestra `antes` / `despues`
- [ ] PATCH persiste en Firestore
- [ ] Agente no pisa `estado_seguimiento` al re-emitir
- [ ] Deduplicación evita duplicados visibles tras reconexión monitor

### Criterios de éxito piloto

| Métrica | Objetivo |
|---------|----------|
| Falsos positivos | < 20% marcados `falso_positivo` |
| Detección monitor | 100% en pruebas conect/desconect |
| Latencia | Evento visible ≤ 10 min desde cambio |
| Pérdida de eventos | 0 (salvo Firestore offline prolongado) |

---

## Fase 7 — Opcional (post-MVP)

Ver **`docs/PLAN_NOTIFICACIONES_HARDWARE_INVENTARIO.md`**.

| Subfase | Entregable |
|---------|------------|
| 7a | Email grupo IT + `notificaciones_enviadas` |
| 7b | Preferencias por usuario IT |
| 7c | Slack/Teams + plantillas editables |
| 7d | Digest diario + escalamiento 24 h |

También opcional v2 agente+inventario:

- [ ] Reportes CSV (cambios no autorizados por mes)
- [ ] Integración tickets (Jira) vía `notas_it` manual en v1

---

## Pendientes de governance (Fase 0)

- [ ] Aprobar `PLAN_AUDITORIA_HARDWARE.md` con jefe / IT
- [ ] Acordar campos exactos y workflow con equipo inventario
- [ ] Comunicar a IT limitaciones (monitores sin serial, debounce v1)

---

## Orden sugerido de trabajo (actualizado)

1. ~~Doc de prueba + modelo Java + GET lista pendientes~~ ✓  
2. ~~PATCH workflow + detalle evento~~ ✓ (falta `revisado_por`)  
3. ~~Badge + timeline en ficha PC~~ ✓  
4. Índices Firestore restantes + reglas `eventos_hardware` en dev  
5. Completar `revisado_por` en PATCH (usuario autenticado)  
6. UI tipada ram / disco / procesador (Fase 4)  
7. Piloto con agente v5.9.0  
8. Prod gradual  

---

## Referencia rápida — archivos implementados

| Capa | Archivos principales |
|------|---------------------|
| Modelo | `inventario/src/main/java/.../models/EventoHardware.java` |
| API | `.../controller/EventoHardwareController.java`, `.../services/EventoHardwareService.java` |
| Front lista | `inventario-front/src/pages/EventosHardwareList.jsx` |
| Front detalle | `inventario-front/src/pages/EventoHardwareDetail.jsx` |
| Timeline PC | `inventario-front/src/components/ComputadoraEventosTimeline.jsx` |
| Badge | `inventario-front/src/components/SidebarNav.jsx` + `hooks/useQueries.js` |

---

*Última actualización: Septiembre 2026 — post implementación Fase 3 MVP en `MiniAgente-Inventario`.*
