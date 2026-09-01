# Análisis de reglas — etiquetas QR

## Accesos

- `computadoras`: listado autenticado, sin escrituras cliente.
- `etiquetas_qr_admin`: listado y lectura autenticados; creación y actualización
  autenticadas.
- `fichas_qr`: lectura individual pública por token; listado solo autenticado;
  creación y actualización autenticadas.

No hay consultas con `where`, `orderBy` ni índices compuestos. El panel descarga
ambas colecciones permitidas y relaciona los registros en memoria.

## Esquema y validaciones

Las dos copias solo aceptan campos conocidos, tipos estrictos y longitudes
limitadas. La ficha administrativa debe coincidir con `hostname` y `ubicacion`
de `computadoras/{machineId}`. La ficha pública debe coincidir con su contraparte
administrativa en la misma operación atómica.

## Revisión adversarial

- Listado público: bloqueado; únicamente `get` de una ficha activa.
- Escritura anónima: bloqueada.
- UUID público: no se almacena en `fichas_qr`.
- Contaminación de esquema y payloads grandes: bloqueados con `hasOnly`, tipos y
  límites de longitud.
- Alteración de hostname/ubicación: bloqueada si no coincide con `computadoras`.
- Cambio de relación a otra PC: `machineId` es inmutable en actualizaciones.
- Manipulación temporal: `creadaEn` es inmutable y `actualizadaEn` debe ser
  `request.time`.
- Bypass entre documento privado y público: la validación usa `getAfter`, por lo
  que ambos deben coincidir al finalizar el batch.
- Enumeración por token: se usan 128 bits aleatorios (`crypto.randomUUID`) y las
  reglas bloquean consultas públicas.

Riesgo residual: cualquier cuenta admitida por Firebase Authentication conserva
los permisos amplios que ya tenía el dashboard sobre `computadoras`. Conviene
restringir el proveedor o introducir roles antes de ampliar el uso fuera del
equipo interno.
