# Cómo tener una URL para descargar el AgenteBacar.exe

Necesitás una URL pública (o con token) donde esté el `.exe` para que el comando **ACTUALIZAR_AGENTE** pueda descargarlo en cada PC. Dos opciones:

---

## Opción 1: Firebase Storage (recomendada, mismo proyecto)

Ya usás Firebase. Podés subir el `.exe` a **Firebase Storage** del mismo proyecto y usar esa URL.

### Pasos

1. **Compilá el exe** (si no lo tenés):
   ```bat
   compilar.bat
   ```
   El archivo queda en `dist\AgenteBacar.exe`.

2. **Entrá a la consola de Firebase**  
   https://console.firebase.google.com → tu proyecto.

3. **Activá Storage** (si no está):  
   Menú izquierdo → **Build** → **Storage** → **Get started** → elegí modo (producción) y región.

4. **Subí el archivo**  
   En Storage → **Files** → **Upload file** → elegí `dist\AgenteBacar.exe`.  
   Podés subirlo a la raíz o en una carpeta, por ejemplo `agente/AgenteBacar.exe`.

5. **Obtener la URL**
   - Clic en el archivo subido → pestaña **URL** (o los tres puntos → “Get download link”).  
   - Esa URL suele traer un token y sirve para descargar.

   **Para una URL fija que no cambie** (recomendado para actualizaciones):
   - En Storage → **Rules**, dejá algo que permita lectura (solo si querés que cualquiera con la URL pueda bajar):
     ```
     rules_version = '2';
     service firebase.storage {
       match /b/{bucket}/o {
         match /agente/{allPaths=**} {
           allow read: if true;   // público solo para esa carpeta
           allow write: if false;
         }
       }
     }
     ```
   - La URL “fija” tiene esta forma (reemplazá `TU_PROYECTO` y la ruta si usaste otra):
     ```
     https://firebasestorage.googleapis.com/v0/b/TU_PROYECTO.appspot.com/o/agente%2FAgenteBacar.exe?alt=media
     ```
   - Si subiste en la raíz y el archivo se llama `AgenteBacar.exe`:
     ```
     https://firebasestorage.googleapis.com/v0/b/TU_PROYECTO.appspot.com/o/AgenteBacar.exe?alt=media
     ```
   El nombre del bucket lo ves en Storage → pestaña “Files” arriba (ej. `minagente-xxxxx.appspot.com`).

6. **Configurá esa URL en Firebase** (documento `config/agente`):
   ```bash
   python set_agente_url.py "https://firebasestorage.googleapis.com/v0/b/TU_PROYECTO.appspot.com/o/agente%2FAgenteBacar.exe?alt=media"
   ```

Listo: cuando ejecutes **ACTUALIZAR_AGENTE** desde la consola, el agente usará esa URL para descargar e instalar.

---

## Opción 2: OneDrive o Google Drive (rápido, menos estable)

- **OneDrive**: Subí el `.exe`, “Compartir” → “Cualquier persona con el vínculo” → copiá el enlace.  
  Para enlace **directo** a descarga, cambiá la URL así:  
  Si el link es `https://1drv.ms/u/s!xxx` → abrilo en el navegador, elige “Descargar” y en “Descargar” podés copiar la URL real, o usar herramientas que convierten el link de OneDrive a directo.

- **Google Drive**: Subí el archivo → clic derecho → Compartir → “Cualquier persona con el enlace” → “Copiar enlace”.  
  La URL de descarga directa tiene otra forma:  
  Si el link es `https://drive.google.com/file/d/FILE_ID/view?usp=sharing`  
  la descarga directa es: `https://drive.google.com/uc?export=download&id=FILE_ID`  
  (reemplazá `FILE_ID` por el ID que aparece en el enlace).

Luego:
```bash
python set_agente_url.py "URL_DIRECTA_QUE_OBTUVISTE"
```

---

## Resumen

| Opción              | Ventaja                          | Desventaja              |
|---------------------|----------------------------------|--------------------------|
| **Firebase Storage**| Mismo proyecto, control total    | Hay que subir a mano o con script |
| **Drive / OneDrive**| Muy rápido                       | URLs a veces inestables o con límites |

Recomendación: **Firebase Storage** (opción 1). Después de tener la URL, ejecutá siempre:

```bash
python set_agente_url.py "TU_URL_AQUI"
```

---

## Cómo ejecutar el nuevo .exe en las máquinas

El agente **no** ejecuta el nuevo .exe por sí solo: vos disparás la actualización desde Firebase. En cada PC el agente está escuchando el documento **tareas/{uuid}**. Cuando ve el comando **ACTUALIZAR_AGENTE**, descarga el .exe desde **config/agente.url**, se reemplaza y reinicia el servicio. Así el nuevo .exe queda corriendo.

### Opción A: Script (recomendado)

Desde tu PC (con el proyecto y auth):

```bash
# Enviar actualización a TODAS las PCs registradas en tareas
python enviar_actualizar_agente.py

# O solo a ciertas PCs (UUIDs)
python enviar_actualizar_agente.py 5859A1A8-C141-0000-0000-000000000000 CC558C80-5224-1208-B779-197243E51900
```

Cada máquina que tenga el agente corriendo (y esté leyendo Firebase) recibirá el comando, descargará el .exe de la URL configurada, se actualizará y reiniciará el servicio.

### Opción B: Firebase Console

1. Entrá a [Firebase Console](https://console.firebase.google.com) → tu proyecto → **Firestore**.
2. Colección **tareas** → abrí el documento cuyo ID es el **UUID de la PC** (el mismo que en **computadoras**).
3. Editá el campo **comando** y poné exactamente: `ACTUALIZAR_AGENTE`.
4. Guardá.

Para cada PC que quieras actualizar repetí con su documento en **tareas** (un doc por UUID).

### Qué pasa en cada máquina

1. El agente (servicio **AgenteMonitoreo**) recibe el comando.
2. Lee la URL de **config/agente**.
3. Descarga el .exe en la misma carpeta como `AgenteBacar_new.exe`.
4. Crea un .bat que: espera unos segundos, para el servicio, reemplaza el .exe, inicia el servicio de nuevo y se borra.
5. El proceso actual termina; el .bat hace el reemplazo y arranca el nuevo .exe. En esa PC ya queda corriendo la nueva versión.

### Cómo saber si se actualizaron

1. **Versión del agente en Firebase**  
   Cada PC envía su versión en el documento **computadoras/{uuid}** (campo **version_agente**). Si en **config** tenés `VERSION = "2.0.1"`, después de mandar ACTUALIZAR_AGENTE las PCs que ya se actualizaron reportarán **version_agente: 2.0.1** en la próxima sincronización (1–2 minutos).

2. **Script de verificación**  
   Ejecutá:
   ```bash
   python verificar_actualizaciones.py
   ```
   Mostrará por cada PC: hostname, **version_agente** y el **último comando** en **tareas**:
   - **ACTUALIZACION_PROGRAMADA**: recibió la orden y programó la actualización.
   - **ACTUALIZAR_AGENTE_ERROR**: falló (revisar el documento en Firestore).
   - **NINGUNO**: en espera o ya reinició con la nueva versión.

   Si la **version_agente** coincide con la versión nueva que subiste, esa PC **ya se actualizó**.

3. **Volcado completo**  
   `python dump_firebase.py` y revisar en `firebase_dump.json` los campos **version_agente** en **computadoras** y **comando** en **tareas**.
