#!/usr/bin/env python3
"""
scripts/security_check.py — Auditoría de los 4 tips de seguridad del proyecto.

USO:
  python scripts/security_check.py

Verifica:
  TIP 1 — DDoS / WAF: firestore.rules y puertos expuestos
  TIP 2 — Credenciales: no commiteadas, en .gitignore
  TIP 3 — No SQL crudo: uso de SDK NoSQL
  TIP 4 — Manejo de errores: cobertura de try/except en puntos críticos
"""

import io
import os
import re
import subprocess
import sys

# Forzar UTF-8 en la salida para evitar errores con caracteres especiales en Windows
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")

_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, _ROOT)

_resultados = []


def check(nombre, ok, detalle="", nivel="error"):
    """Registra un check. nivel puede ser 'error' o 'warn'."""
    if ok:
        icon = "OK  "
        color = "\033[32m"
    elif nivel == "warn":
        icon = "WARN"
        color = "\033[33m"
    else:
        icon = "FAIL"
        color = "\033[31m"
    reset = "\033[0m"
    linea = f"  [{color}{icon}{reset}] {nombre}"
    if detalle:
        linea += f"\n         → {detalle}"
    print(linea)
    _resultados.append((ok, nivel, nombre))


def _leer(relpath):
    try:
        with open(os.path.join(_ROOT, relpath), encoding="utf-8") as f:
            return f.read()
    except FileNotFoundError:
        return None


_ESTE_ARCHIVO = os.path.abspath(__file__)


def _grep_src(patron, extensiones=(".py",), excluir_self=True):
    """Busca un patrón regex en todos los archivos Python del proyecto."""
    encontrados = []
    for raiz, _, archivos in os.walk(_ROOT):
        raiz_rel = os.path.relpath(raiz, _ROOT)
        if any(parte in raiz_rel.split(os.sep) for parte in ("build", "dist", ".venv", "__pycache__")):
            continue
        for archivo in archivos:
            if not any(archivo.endswith(ext) for ext in extensiones):
                continue
            ruta = os.path.join(raiz, archivo)
            if excluir_self and os.path.abspath(ruta) == _ESTE_ARCHIVO:
                continue
            try:
                with open(ruta, encoding="utf-8", errors="ignore") as f:
                    for i, linea in enumerate(f, 1):
                        if re.search(patron, linea, re.IGNORECASE):
                            rel = os.path.relpath(ruta, _ROOT)
                            encontrados.append(f"{rel}:{i}  {linea.rstrip()}")
            except OSError:
                pass
    return encontrados


def _git(cmd):
    """Ejecuta un comando git y devuelve stdout como string."""
    try:
        r = subprocess.run(
            cmd, shell=True, capture_output=True, text=True, encoding="utf-8",
            errors="replace", cwd=_ROOT
        )
        return r.stdout.strip()
    except Exception:
        return ""


# =============================================================================
print()
print("=" * 65)
print("  security_check.py — Auditoría de seguridad MiniAgente")
print("=" * 65)

# =============================================================================
print()
print("── TIP 1: DDoS / Firestore Rules / Sin puertos expuestos ──────")

# 1a. firestore.rules existe
rules_texto = _leer("firestore.rules")
check("firestore.rules existe en el repo", rules_texto is not None,
      "Crealo y desplegalo con: firebase deploy --only firestore:rules" if rules_texto is None else "")

if rules_texto:
    # 1b. No hay ninguna colección con acceso público (allow ... if true)
    lineas_publicas = [
        l.strip() for l in rules_texto.splitlines()
        if re.search(r"allow\s+(read|write|read,\s*write|write,\s*read)\s*:\s*if\s+true", l)
    ]
    check(
        "Sin colecciones con acceso público (allow ... if true)",
        len(lineas_publicas) == 0,
        "Reglas peligrosas: " + " | ".join(lineas_publicas) if lineas_publicas else "",
    )

    # 1c. config/ está bloqueada
    bloque_config = re.search(
        r'match\s*/config/\{[^}]+\}[^}]*allow\s+read,\s*write\s*:\s*if\s+false', rules_texto, re.DOTALL
    )
    check(
        "config/ bloqueada para clientes (read, write: if false)",
        bloque_config is not None,
        "La colección config/ debería tener allow read, write: if false" if not bloque_config else "",
    )

    # 1d. computadoras/ escritura bloqueada para clientes
    bloque_comp_write = re.search(
        r'match\s*/computadoras/\{[^}]+\}\s*\{[^}]*allow\s+write\s*:\s*if\s+false', rules_texto, re.DOTALL
    )
    check(
        "computadoras/ escritura bloqueada para clientes",
        bloque_comp_write is not None,
        "Ningún cliente debería poder escribir datos de hardware directamente" if not bloque_comp_write else "",
    )

# 1e. No hay servidor HTTP expuesto
patrones_server = r"(socket\.listen|app\.run|uvicorn\.|http\.server|Flask|FastAPI|tornado|aiohttp\.web)"
ocurrencias_server = _grep_src(patrones_server)
# Excluir comentarios y esta misma línea
ocurrencias_server = [o for o in ocurrencias_server if not re.match(r'\s*#', o.split("  ", 1)[-1])]
check(
    "No hay servidor HTTP expuesto (no Flask/uvicorn/socket.listen)",
    len(ocurrencias_server) == 0,
    "Encontrado en: " + ", ".join(ocurrencias_server[:3]) if ocurrencias_server else "",
)


# =============================================================================
print()
print("── TIP 2: Credenciales no expuestas ───────────────────────────")

# 2a. auth/ está en .gitignore
gitignore = _leer(".gitignore") or ""
check(
    "auth/ está en .gitignore",
    "auth/" in gitignore,
    "Agregá 'auth/' a .gitignore" if "auth/" not in gitignore else "",
)

# 2b. serviceAccountKey.json está en .gitignore
check(
    "serviceAccountKey.json está en .gitignore",
    "serviceAccountKey.json" in gitignore,
    "Agregá 'serviceAccountKey.json' a .gitignore" if "serviceAccountKey.json" not in gitignore else "",
)

# 2c. auth/*.json no está tracked en git
tracked = _git('git ls-files auth/')
check(
    "auth/*.json no está tracked en git (git ls-files auth/)",
    tracked == "",
    f"Archivo tracked: {tracked} — Ejecutá: git rm --cached {tracked}" if tracked else "",
)

# 2d. auth/*.json no aparece en el historial de commits
historial = _git('git log --all --full-history --oneline -- "auth/*.json"')
check(
    "auth/*.json nunca fue commiteado (historial limpio)",
    historial == "",
    "Fue commiteado en: " + historial[:120] if historial else "",
    nivel="warn",
)

# 2e. No hay credenciales hardcodeadas en código fuente
# Busca valores literales (strings), no variables que almacenan una clave generada en memoria
patrones_creds = r'(private_key\s*["\']|client_email\s*["\']|-----BEGIN (RSA |EC )?PRIVATE KEY)'
ocurrencias_creds = _grep_src(patrones_creds)
check(
    "Sin private_key/client_email hardcodeados en código",
    len(ocurrencias_creds) == 0,
    "Encontrado en: " + " | ".join(ocurrencias_creds[:3]) if ocurrencias_creds else "",
)

# 2f. FIREBASE_JSON_PATH usa variable de entorno o path relativo (no expone credenciales en red)
config_texto = _leer("config/config.py") or ""
usa_env_var = "os.environ" in config_texto or "os.getenv" in config_texto
check(
    "FIREBASE_JSON_PATH configurado (archivo local o env var)",
    "FIREBASE_JSON_PATH" in config_texto,
    "No se encontró FIREBASE_JSON_PATH en config/config.py" if "FIREBASE_JSON_PATH" not in config_texto else "",
    nivel="warn",
)


# =============================================================================
print()
print("── TIP 3: Sin SQL crudo — SDK NoSQL ───────────────────────────")

# 3a. No hay imports de librerías SQL
patrones_sql_import = r"import\s+(sqlite3|psycopg2|pymysql|cx_Oracle|pyodbc|MySQLdb)"
ocurrencias_sql_import = _grep_src(patrones_sql_import)
check(
    "Sin imports de librerías SQL (sqlite3, psycopg2, pymysql...)",
    len(ocurrencias_sql_import) == 0,
    "Encontrado: " + " | ".join(ocurrencias_sql_import[:3]) if ocurrencias_sql_import else "",
)

# 3b. No hay queries SQL crudas
patrones_sql_query = r"(cursor\.execute|\.executemany|SELECT\s+\*\s+FROM|INSERT\s+INTO|DROP\s+TABLE)"
ocurrencias_sql_query = _grep_src(patrones_sql_query)
# Excluir comentarios
ocurrencias_sql_query = [o for o in ocurrencias_sql_query
                         if not re.match(r'[^"]*#', o.split("  ", 1)[-1].split(":", 1)[-1])]
check(
    "Sin queries SQL crudas (SELECT, INSERT, cursor.execute...)",
    len(ocurrencias_sql_query) == 0,
    "Encontrado: " + " | ".join(ocurrencias_sql_query[:3]) if ocurrencias_sql_query else "",
)

# 3c. Usa Firestore SDK
usa_firestore_sdk = bool(_grep_src(r"from google\.cloud import firestore|import firebase_admin"))
check(
    "Usa Firestore SDK (equivalente a ORM para NoSQL)",
    usa_firestore_sdk,
    "No se detectó uso del SDK de Firestore en el proyecto" if not usa_firestore_sdk else "",
)


# =============================================================================
print()
print("── TIP 4: Manejo de errores en puntos críticos ─────────────────")

main_texto = _leer("main.py") or ""
firebase_texto = _leer("src/database/firebase_client.py") or ""
auto_update_texto = _leer("src/core/auto_update.py") or ""

# 4a. SvcDoRun tiene try/except cubriendo el loop principal
tiene_try_svcrun = "def SvcDoRun" in main_texto and "except Exception as e:" in main_texto
check(
    "SvcDoRun tiene try/except cubriendo el loop principal",
    tiene_try_svcrun,
    "El loop del servicio puede caer silenciosamente sin try/except" if not tiene_try_svcrun else "",
)

# 4b. on_snapshot tiene try/except interno
tiene_try_snapshot = "def on_snapshot" in firebase_texto and (
    "try:" in firebase_texto[firebase_texto.find("def on_snapshot"):firebase_texto.find("def on_snapshot") + 2000]
)
check(
    "on_snapshot() tiene try/except interno",
    tiene_try_snapshot,
    "Un error en el listener puede dejar de recibir comandos remotos" if not tiene_try_snapshot else "",
)

# 4c. requests.get en auto_update tiene try/except
idx_requests = auto_update_texto.find("requests.get")
if idx_requests >= 0:
    fragmento = auto_update_texto[max(0, idx_requests - 500):idx_requests + 200]
    tiene_try_http = "try:" in fragmento
    check(
        "requests.get (descarga del agente) está dentro de try/except",
        tiene_try_http,
        "La llamada HTTP puede lanzar excepción sin captura" if not tiene_try_http else "",
    )
else:
    check("requests.get presente en auto_update.py", False,
          "No se encontró requests.get — verificar manualmente", nivel="warn")

# 4d. Hay logging centralizado a Firestore (no solo archivos locales)
tiene_log_centralizado = "log_centralizado" in firebase_texto and "cyberwatch_logs" in firebase_texto
check(
    "Logging centralizado a Firestore (log_centralizado / cyberwatch_logs)",
    tiene_log_centralizado,
    "Los errores solo se loggean localmente, no son visibles en el dashboard" if not tiene_log_centralizado else "",
)

# 4e. No hay bloques bare 'except: pass' que oculten errores silenciosamente
bare_except = _grep_src(r"^\s*except\s*:\s*(pass|\.\.\.)\s*$")
# Permitir algunos en arranque crítico (main.py) — avisar si hay muchos
check(
    f"Sin 'except: pass' silenciosos ({len(bare_except)} encontrados)",
    len(bare_except) <= 3,
    "Ubicaciones: " + " | ".join(bare_except[:5]) if bare_except else "",
    nivel="warn",
)

# 4f. Hay retry logic para errores transitorios de Firestore
tiene_retry = "_ejecutar_con_reintento" in firebase_texto or "_es_error_transitorio" in firebase_texto
check(
    "Retry logic para errores transitorios de Firestore (503/504)",
    tiene_retry,
    "Los errores de red pueden hacer caer el agente sin reintentos" if not tiene_retry else "",
)


# =============================================================================
print()
print("── TIP 7: Validación de datos / comandos remotos ──────────────")

# 7a. Comandos remotos: solo whitelist conocida (no ejecuta strings arbitrarios)
comandos_conocidos = ["ACTUALIZAR_DATOS", "INSTALAR_UPDATES", "ACTUALIZAR_AGENTE", "RESETEAR_ID"]
todos_presentes = all(f'comando == "{c}"' in firebase_texto for c in comandos_conocidos)
check(
    "Comandos remotos validados contra whitelist conocida",
    todos_presentes,
    "Verificar que solo se ejecutan comandos conocidos en on_snapshot()" if not todos_presentes else "",
)

# 7b. ACTUALIZAR_AGENTE tiene validación de antigüedad (anti-replay)
_antiplay_ok = "UPDATE_COMMAND_MAX_AGE_SECONDS" in firebase_texto and "edad_seg" in firebase_texto
check(
    "ACTUALIZAR_AGENTE tiene validación de antigüedad (anti-replay)",
    _antiplay_ok,
    "Sin anti-replay, un comando capturado puede re-ejecutarse" if not _antiplay_ok else "",
)

# 7c. No hay eval() / exec() aplicado a datos externos
ocurrencias_eval = _grep_src(r"\beval\s*\(|\bexec\s*\(")
check(
    "Sin eval()/exec() sobre datos externos",
    len(ocurrencias_eval) == 0,
    "Encontrado en: " + " | ".join(ocurrencias_eval[:3]) if ocurrencias_eval else "",
)

# 7d. El campo comando se valida como string antes de comparar
valida_string = "isinstance(raw, str)" in firebase_texto or "str(raw)" in firebase_texto
check(
    "Campo 'comando' se convierte a string antes de comparar",
    valida_string,
    "Un tipo inesperado (dict, int) en el campo comando podría causar comportamiento impredecible" if not valida_string else "",
)


# =============================================================================
print()
print("── TIP 8: Tareas largas no bloquean el servicio ────────────────")

# 8a. INSTALAR_UPDATES corre en el thread del listener de Firestore (background)
# La función on_snapshot es llamada por el SDK en un thread separado — es correcto
instalar_en_snapshot = ("elif comando == \"INSTALAR_UPDATES\"" in firebase_texto and
                        "def on_snapshot" in firebase_texto)
check(
    "INSTALAR_UPDATES corre en thread background (listener Firestore)",
    instalar_en_snapshot,
    "Si corre en el hilo principal, bloquea el ciclo de sync de 5 min" if not instalar_en_snapshot else "",
)

# 8b. download_and_apply_update corre en thread separado
usa_thread_descarga = "threading.Thread" in main_texto and "_hilo_descarga" in main_texto
check(
    "download_and_apply_update corre en thread separado (no bloquea el loop)",
    usa_thread_descarga,
    "La descarga del agente bloquea el hilo principal hasta 120s — considerar thread separado" if not usa_thread_descarga else "",
    nivel="warn",
)

# 8c. El ciclo de sync de datos (5 min) no tiene operaciones bloqueantes innecesarias
# Verificar que obtener_datos_pc() no tiene sleeps largos (solo WaitForMultipleObjects con timeout)
tiene_wait_correcto = "WaitForMultipleObjects" in main_texto or "WaitForSingleObject" in main_texto
check(
    "Loop principal usa WaitForMultipleObjects (no busy-wait ni sleep largo)",
    tiene_wait_correcto,
    "El loop principal debería usar WaitForSingleObject/WaitForMultipleObjects para evitar CPU spin" if not tiene_wait_correcto else "",
)


# =============================================================================
print()
print("=" * 65)
ok_count = sum(1 for ok, nivel, _ in _resultados if ok)
warn_count = sum(1 for ok, nivel, _ in _resultados if not ok and nivel == "warn")
fail_count = sum(1 for ok, nivel, _ in _resultados if not ok and nivel == "error")
total = len(_resultados)

print(f"  Resultado: {ok_count}/{total} OK  |  {warn_count} advertencias  |  {fail_count} fallos")
if fail_count == 0 and warn_count == 0:
    print("  \033[32mTodos los controles pasaron correctamente.\033[0m")
elif fail_count == 0:
    print("  \033[33mSin fallos críticos. Revisar advertencias arriba.\033[0m")
else:
    print("  \033[31mHay fallos que requieren atención. Ver detalle arriba.\033[0m")
print("=" * 65)
print()

sys.exit(0 if fail_count == 0 else 1)
