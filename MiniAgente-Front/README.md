# MiniAgente-Front — HW Dashboard

Cliente web para consultar en tiempo casi real los datos que el **agente Windows** sube a **Firebase Firestore** (colección `computadoras` y colecciones asociadas).

Stack: **React 19**, **TypeScript**, **Vite 8**, **react-router-dom**, **lucide-react** (iconos del menú), **Firebase** (Firestore cliente).

---

## Requisitos

- Node.js 20+ (recomendado; compatible con Vite 8)
- Proyecto Firebase con Firestore habilitado (el mismo que usa `firebase_client.py` del agente)

---

## Configuración

Creá un archivo **`.env.local`** en esta carpeta (no se sube al repo; está en `.gitignore`) con la config web de Firebase:

```env
VITE_FIREBASE_API_KEY=tu_api_key
VITE_FIREBASE_AUTH_DOMAIN=tu-proyecto.firebaseapp.com
VITE_FIREBASE_PROJECT_ID=tu-proyecto
VITE_FIREBASE_STORAGE_BUCKET=tu-proyecto.appspot.com
VITE_FIREBASE_MESSAGING_SENDER_ID=...
VITE_FIREBASE_APP_ID=...
```

Los valores salen de **Firebase Console → Configuración del proyecto → Tus apps → SDK de configuración**.

La app comprueba en runtime si faltan variables; sin ellas verás error o mensaje de configuración incompleta (`src/lib/firebase.ts`).

---

## Scripts

| Comando | Uso |
|---------|-----|
| `npm install` | Dependencias |
| `npm run dev` | Servidor de desarrollo (HMR) |
| `npm run build` | `tsc -b` + build de producción en `dist/` |
| `npm run preview` | Servir el `dist/` localmente |
| `npm run lint` | ESLint |

---

## Rutas

Definidas en `src/App.tsx`:

| Ruta | Pantalla |
|------|----------|
| `/` | **Dashboard** — vista resumida del parque |
| `/inventario` | **Inventario** — tabla plana de ítems por equipo |
| `/computadoras` | **Computadoras** — listado y modal de detalle por PC |
| `/tareas` | **Tareas** — seguimiento de tareas/comandos |

Layout común: `src/pages/Layout.tsx` (sidebar + outlet).

---

## Inventario (`/inventario`)

Expande cada documento de `computadoras` en **filas** mezclando hardware interno y periféricos (misma fuente que el agente ya persiste).

| Tipo de fila (UI) | Datos en Firestore |
|-------------------|-------------------|
| **CPU** | `procesador`; detalles: SO (`sistema_operativo` / `so`) |
| **RAM** | `modulos_ram` (una fila por módulo); si no hay módulos, resumen con `ram_total_gb` |
| **Disco SSD** / **Disco duro** / **Disco (tipo desconocido)** | `discos[]`: agrupación por `disco_fisico_index` para no duplicar el mismo disco por cada letra de unidad; `tipo_disco` del agente (`SSD` / `HDD` / otro) |
| **Monitor, Teclado, Mouse, …** | `perifericos` (monitores, `dispositivos_usb`, impresoras, audio); en teclado/mouse consolidados puede venir `conexion` (`usb`, `inalambrico_usb`, `bluetooth`) |

**Filtros:** chips y desplegable por tipo; **búsqueda** por hostname, modelo, detalles y etiquetas (p. ej. “ssd”, “duro”).

Implementación principal: `src/pages/Inventario.tsx`. Tipos de documento: `src/types/firestore.ts` (`HWComputadora`, `HWDisco`, `HWPerifericos`, …).

---

## Otras pantallas (resumen)

- **Dashboard** (`src/pages/Dashboard.tsx`): métricas y listados agregados según lo expuesto en el hook de datos.
- **Computadoras** (`src/pages/Computadoras.tsx`): foco en una PC; muestra periféricos USB con `conexion` cuando existe; en **Red** muestra SSID Wi‑Fi (`wifi_ssid`), perfil/categoría por adaptador (`perfil_red`, `categoria_red`) e IPs.
- **Tareas** (`src/pages/Tareas.tsx`): tareas Firestore según el modelo del proyecto.

Datos: hook `src/hooks/useComputadorasHW.ts` y lecturas Firestore acordes a las reglas de seguridad del proyecto.

---

## Despliegue

El build estático (`npm run build`) genera `dist/`. Podés servirlo con cualquier hosting estático (Firebase Hosting, nginx, etc.), configurando las variables `VITE_*` **en tiempo de build** (no en runtime en el navegador, salvo que el hosting inyecte HTML).

---

## Documentación del monorepo

El agente, campos de Firestore y compilación del `.exe` están descritos en el **`README.md` de la raíz** del repositorio (`../README.md`).
