# Reglas y lecciones aprendidas del proyecto

Este archivo es leído automáticamente al inicio de cada conversación.
Contiene reglas de comportamiento obligatorias y lecciones aprendidas del proyecto.

---

## Flujo de trabajo: discutir antes de actuar

Cuando el usuario mencione una idea, problema o posible cambio — sin importar el tipo de acción (código, arquitectura, configuración, comandos, etc.) — NO lo implementes directamente.

**Procedimiento obligatorio:**
1. Presentar el razonamiento: qué harías, por qué, y cómo quedaría.
2. Esperar aprobación explícita del usuario. Cuando el usuario diga "apruebo", "está bien", o similar — ejecutar directamente sin pedir confirmación adicional.

---

## Cambios mínimos: solo lo solicitado

Realizá únicamente el cambio que se solicita. No modifiques otras partes del código, no refactorices, no cambies estilos globales ni estructuras existentes. Si considerás que algo más debería cambiarse, primero sugerilo antes de hacerlo. Mantené intacto todo lo que no esté directamente relacionado con el requerimiento.

---

## Consultar README.md al inicio de cada conversación

Al comenzar cualquier tarea, leer `README.md` en la raíz del repo para tener el contexto actualizado del proyecto: arquitectura, estado actual, bugs abiertos y pendientes.

**Regla:** Antes de proponer cualquier cambio, verificar si el README tiene información relevante sobre el componente o área que se va a modificar.

---

## Mantener README.md actualizado

Cada vez que se implemente un cambio significativo (nueva feature, fix de bug, cambio arquitectónico, nuevo pendiente resuelto), actualizar `README.md` para reflejar el estado actual del proyecto.

**Qué actualizar según el caso:**
- Bug resuelto → removerlo de "Bugs abiertos" o marcarlo como resuelto
- Nueva funcionalidad → agregarla en la sección correspondiente (arquitectura, colecciones, comandos, logs)
- Pendiente completado → removerlo de "Refactoring pendiente"
- Cambio de paths, nombres o comportamiento → actualizar tablas y descripciones

**Regla:** El README es la fuente de verdad del estado del proyecto. Si el código cambió, el README debe reflejar ese cambio.

---

## Verificar documentación antes de implementar

Antes de realizar cualquier cambio técnico (código, configuración, comandos, dependencias, etc.):

1. Buscar la documentación más reciente disponible sobre la tecnología o API involucrada.
2. Implementar **solo** si hay certeza de que funcionará con las versiones actuales del proyecto.

**Por qué:** Evita introducir código obsoleto o con APIs deprecadas que pasen los tests locales pero fallen en producción.

---

## Recordar push antes del release

Al terminar de implementar una funcionalidad o fix, SIEMPRE recordar al usuario:

> "Antes de hacer el release, no olvides hacer `git push` para que el código esté en el repositorio remoto."

**Por qué:** El deploy remoto descarga el ZIP desde una URL (GitHub Releases). Si el código no fue pusheado y taggeado antes de crear el release, el ZIP no incluirá los cambios nuevos.

---

## Firebase Storage: no usar PredefinedObjectAcl.PublicRead

**Error cometido:** Al subir archivos a Firebase Storage con `Google.Cloud.Storage.V1`,
se usó `PredefinedObjectAcl.PublicRead` en las opciones de upload:

```csharp
await storageClient.UploadObjectAsync(bucket, objectName, "image/png", fileStream,
    new UploadObjectOptions { PredefinedAcl = PredefinedObjectAcl.PublicRead }); // ❌
```

**Por qué falla:** Los buckets de Firebase Storage tienen "Uniform bucket-level access"
activado por defecto, que deshabilita los ACLs a nivel de objeto. Esto lanza una
`GoogleApiException` que es capturada silenciosamente, impidiendo la ejecución del
código posterior (actualización de Firestore).

**Fix correcto:** Subir sin ACL y generar una URL firmada (signed URL):

```csharp
await storageClient.UploadObjectAsync(bucket, objectName, "image/png", fileStream); // ✅

var urlSigner = UrlSigner.FromCredential(credential);
var url = await urlSigner.SignAsync(bucket, objectName, TimeSpan.FromDays(365)); // ✅
```

**También:** Usar `SetAsync(..., SetOptions.MergeAll)` en lugar de `UpdateAsync`
para Firestore, ya que `UpdateAsync` lanza si el documento no existe.

---

## Machine ID: usar UUID de hardware (WMI), no Guid.NewGuid()

**Error cometido:** Se recomendó usar `Guid.NewGuid()` como identificador de máquina,
guardado en `cyberwatch_machine_id.txt`. Esto genera duplicados en Firestore si el
archivo se borra, el servicio se reinstala, o cambia el directorio de instalación.
Cada reinstalación crea un documento huérfano en `cyberwatch_instancias`.

**Fix correcto:** Derivar el ID del UUID de hardware de la máquina via WMI, que es
estable entre reinstalaciones:

```csharp
// Requiere paquete: System.Management
using var searcher = new ManagementObjectSearcher("SELECT UUID FROM Win32_ComputerSystemProduct");
foreach (ManagementObject obj in searcher.Get())
{
    var uuid = obj["UUID"]?.ToString()?.Trim().ToLower();
    if (!string.IsNullOrEmpty(uuid) && uuid != "ffffffff-ffff-ffff-ffff-ffffffffffff")
        return uuid;
}
// Fallback: Guid.NewGuid() guardado en archivo
```

**Regla:** Para cualquier identificador que deba ser estable por máquina física,
usar siempre UUID de hardware. Nunca confiar en archivos locales como fuente
de identidad única.

---

## Error en release: verificar si la clave fue expuesta

Si el `git push` o el workflow de GitHub Actions falla con un error relacionado a secretos o credenciales, verificar primero si el archivo `auth/serviceAccountKey.json` (u otro archivo con credenciales) fue incluido accidentalmente en algún commit.

**Síntomas típicos:**
- GitHub bloquea el push con "GH013: Repository rule violations found" / "Push cannot contain secrets"
- El workflow falla por credenciales inválidas o revocadas

**Procedimiento:**
1. Revisar el historial reciente con `git log --name-only` para detectar si se committeó algún archivo de `auth/`
2. Si fue expuesto: rotar la service account en Google Cloud Console (IAM → Service Accounts → crear nueva key, revocar la anterior) y actualizar el secret `FIREBASE_SERVICE_ACCOUNT_B64` en GitHub
3. Limpiar el commit que contiene el secreto antes de pushear:
   ```bash
   git rm --cached auth/<archivo>.json
   echo "auth/" >> .gitignore
   git add .gitignore
   git commit --amend --no-edit
   git push origin main
   ```

**Regla:** El directorio `auth/` nunca debe aparecer en `git status` como staged o committed. Si aparece, detener y seguir el procedimiento anterior.

---

## Publish self-contained: incluir archivos de configuración

**Error cometido:** Al generar el comando `dotnet publish` con `PublishSingleFile`,
no se mencionaron los archivos de configuración necesarios (`appsettings.json`,
`serviceAccountKey.json`). Estos archivos tienen `CopyToOutputDirectory` en el
`.csproj` pero NO se embeben dentro del single-file — quedan como archivos sueltos
que deben estar junto al `.exe`.

**Regla:** Al dar comandos de publish/deploy, SIEMPRE recordar que estos archivos
deben estar en la carpeta de salida:
- `appsettings.json` (configuración de Firebase, umbrales, etc.)
- `serviceAccountKey.json` (credenciales de Firebase)
- `install.bat` (si aplica, para registrar el servicio)

**Comando completo de publish (self-contained, single-file, ambos servicios):**

```bash
dotnet publish CyberWatch.Service/CyberWatch.Service.csproj -c Release -r win-x64 --self-contained true -p:PublishSingleFile=true -o ./publish && dotnet publish CyberWatch.UserAgent/CyberWatch.UserAgent.csproj -c Release -r win-x64 --self-contained true -p:PublishSingleFile=true -o ./publish && cp auth/serviceAccountKey.json ./publish/ && cp CyberWatch.Service/appsettings.json ./publish/
```

**Nota:** `appsettings.json` se copia automáticamente por `CopyToOutputDirectory` del `.csproj`.
`serviceAccountKey.json` no está en el `.csproj`, se copia manualmente.
`install.bat` se copia por el target `CopiarInstaller` del Service `.csproj`.
