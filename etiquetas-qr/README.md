# Etiquetas QR

Módulo web independiente para identificar físicamente las computadoras durante
traslados. Cada etiqueta contiene un QR con un token aleatorio. Al escanearlo,
cualquier persona puede ver únicamente:

- hostname;
- ubicación.

La ficha pública no expone el UUID de la máquina, IP, usuario, software,
telemetría ni otros datos del agente.

## Flujo

1. Un usuario autorizado ingresa con Google en `/`.
2. El módulo lee `computadoras` y copia `hostname` + `ubicacion`.
3. Se generan dos documentos con el mismo token:
   - `etiquetas_qr_admin/{token}`: relación privada con la computadora;
   - `fichas_qr/{token}`: ficha pública mínima.
4. La etiqueta apunta a `/e/{token}` y puede imprimirse desde el navegador.

Las escrituras se realizan en un batch. Las reglas validan los datos contra el
documento original en `computadoras/{machineId}` y no permiten listados públicos.

## Desarrollo

```powershell
npm install
npm run dev
```

## Verificación

```powershell
npm run lint
npm run build
```

Antes de usar el módulo, desplegar y revisar las reglas desde la raíz:

```powershell
npx -y firebase-tools@latest deploy --only firestore:rules --project devbac-42d14
```

El proveedor Google debe estar habilitado en Firebase Authentication para el
panel de administración. El escaneo de las fichas no requiere iniciar sesión.

## Despliegue web

El módulo todavía no tiene un sitio de Firebase Hosting asignado. Al configurarlo,
la aplicación necesita una reescritura SPA hacia `index.html` para que las rutas
`/e/{token}` funcionen al abrirlas directamente.
# React + TypeScript + Vite

This template provides a minimal setup to get React working in Vite with HMR and some Oxlint rules.

Currently, two official plugins are available:

- [@vitejs/plugin-react](https://github.com/vitejs/vite-plugin-react/blob/main/packages/plugin-react) uses [Oxc](https://oxc.rs)
- [@vitejs/plugin-react-swc](https://github.com/vitejs/vite-plugin-react/blob/main/packages/plugin-react-swc) uses [SWC](https://swc.rs/)

## React Compiler

The React Compiler is not enabled on this template because of its impact on dev & build performances. To add it, see [this documentation](https://react.dev/learn/react-compiler/installation).

## Expanding the Oxlint configuration

If you are developing a production application, we recommend enabling type-aware lint rules by installing `oxlint-tsgolint` and editing `.oxlintrc.json`:

```json
{
  "$schema": "./node_modules/oxlint/configuration_schema.json",
  "plugins": ["react", "typescript", "oxc"],
  "options": {
    "typeAware": true
  },
  "rules": {
    "react/rules-of-hooks": "error",
    "react/only-export-components": ["warn", { "allowConstantExport": true }]
  }
}
```

See the [Oxlint rules documentation](https://oxc.rs/docs/guide/usage/linter/rules) for the full list of rules and categories.
