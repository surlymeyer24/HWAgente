import firebase_admin
from firebase_admin import credentials, firestore
from google.api_core import exceptions as google_api_exceptions
import json
import hashlib
import os
import platform
import sys
import time
from urllib.parse import urlparse

# Para ACTUALIZAR_AGENTE: el listener escribe aquí la información y despierta al bucle
_info_actualizacion_pendiente_list = [{}]

# Referencia fuerte al Watch de Firestore (si se pierde, el listener puede cortarse por GC)
_tareas_snapshot_watch = None

# Firestore: URL de actualización AgenteBacar (doc agente_hw). Legacy: config/agente solo url.
CONFIG_DOC_AGENTE_HW = "agente_hw"
CONFIG_DOC_AGENTE_LEGACY = "agente"

def _info_actualizacion_pendiente():
    info = _info_actualizacion_pendiente_list[0]
    _info_actualizacion_pendiente_list[0] = {}
    return info

def _leer_url_y_meta_actualizacion_agente():
    """
    Prioridad: config/agente_hw (url + version opcional informativa),
    luego config/agente (solo url) para agentes antiguos / espejo manual.
    La URL es validada antes de retornarse: si no pasa los controles de
    seguridad (protocolo, dominio, IPs privadas), se retorna url="" y
    se agrega 'url_rechazada_motivo' al dict meta.
    """
    doc_hw = db.collection("config").document(CONFIG_DOC_AGENTE_HW).get()
    doc_legacy = db.collection("config").document(CONFIG_DOC_AGENTE_LEGACY).get()
    cfg_hw = bool(doc_hw and doc_hw.exists)
    cfg_legacy = bool(doc_legacy and doc_legacy.exists)
    url = ""
    version_publicada = None
    origen = None
    sha256_esperado = None
    firma_esperada = None
    if cfg_hw:
        d = doc_hw.to_dict() or {}
        url = (d.get("url") or "").strip()
        vp = (d.get("version") or "").strip()
        version_publicada = vp if vp else None
        sha2 = (d.get("sha256") or "").strip()
        sha256_esperado = sha2.lower() if sha2 else None
        fm = (d.get("firma") or "").strip()
        firma_esperada = fm if fm else None
        if url:
            origen = CONFIG_DOC_AGENTE_HW
    if not url and cfg_legacy:
        d = doc_legacy.to_dict() or {}
        url = (d.get("url") or "").strip()
        if url:
            origen = CONFIG_DOC_AGENTE_LEGACY

    # --- Validación de seguridad de la URL ---
    url_rechazada_motivo = None
    if url:
        try:
            from src.core.auto_update import _validar_url_segura
            motivo = _validar_url_segura(url)
            if motivo:
                url_rechazada_motivo = motivo
                log_debug(f"_leer_url: URL rechazada por seguridad: {motivo} | url={url[:80]}")
                url = ""  # No encolar una URL maliciosa
        except Exception as e:
            log_debug(f"_leer_url: error al validar URL: {e}")

    meta = {
        "origen_config": origen,
        "version_publicada_config": version_publicada,
        "sha256_esperado": sha256_esperado,
        "firma_esperada": firma_esperada,
        "config_agente_hw_existe": cfg_hw,
        "config_agente_legacy_existe": cfg_legacy,
    }
    if url_rechazada_motivo:
        meta["url_rechazada_motivo"] = url_rechazada_motivo
    return url, meta


def _url_actualizacion_pendiente():
    # Fallback legacy
    u = _info_actualizacion_pendiente_list[0].get("url")
    if u:
        _info_actualizacion_pendiente_list[0] = {}
    return u

def _obtener_hostname():
    """Nombre de la PC; fiable cuando el .exe corre como servicio."""
    name = platform.node() or os.environ.get("COMPUTERNAME") or os.environ.get("HOSTNAME")
    if name and name.strip():
        return name.strip()
    if sys.platform == "win32":
        try:
            import ctypes
            buf = ctypes.create_unicode_buffer(256)
            n = ctypes.c_ulong(256)
            if ctypes.windll.kernel32.GetComputerNameW(ctypes.byref(buf), ctypes.byref(n)):
                return buf.value
        except Exception:
            pass
    return "PC-Desconocida"

def log_debug(mensaje):
    try:
        path = "C:\\agente_debug.txt" if os.path.exists("C:\\") else "agente_debug.txt"
        with open(path, "a", encoding='utf-8') as f:
            f.write(f"{time.ctime()}: [Firebase] {mensaje}\n")
    except:
        pass


def _verificar_y_reparar_conectividad():
    """Verifica HTTPS saliente; si falla, agrega regla de firewall para este exe y reintenta."""
    import urllib.request
    import subprocess as _sp

    def _puede_conectar():
        try:
            urllib.request.urlopen("https://firestore.googleapis.com", timeout=5)
            return True
        except Exception:
            return False

    if _puede_conectar():
        return

    log_debug(
        "FIREWALL_CHECK — prueba HTTPS (urllib) a firestore.googleapis.com falló; "
        "intentando regla de firewall (Firestore Admin usa gRPC/HTTP2: puede fallar aunque esto pase)"
    )

    exe_path = sys.executable
    try:
        cmd = (
            f'netsh advfirewall firewall add rule '
            f'name="AgenteBacar_Salida" dir=out action=allow '
            f'program="{exe_path}" enable=yes'
        )
        res = _sp.run(
            cmd, shell=True, capture_output=True, text=True,
            encoding="utf-8", errors="replace",
            creationflags=_sp.CREATE_NO_WINDOW,
        )
        if res.returncode == 0:
            log_debug(f"FIREWALL_REGLA_AGREGADA — {exe_path}")
        else:
            log_debug(f"FIREWALL_REGLA_ERROR — rc={res.returncode} | {res.stdout.strip()} | {res.stderr.strip()}")
    except Exception as e:
        log_debug(f"FIREWALL_REGLA_EXCEPCION — {e}")

    if _puede_conectar():
        log_debug("FIREWALL_CHECK — conectividad restaurada tras agregar regla")
    else:
        log_debug(
            "FIREWALL_CHECK — la prueba HTTPS (urllib) sigue fallando "
            "(firewall corporativo, proxy o TLS); el agente intentará Firestore por gRPC de todas formas"
        )


# UUID de la máquina, se setea desde main.py al arrancar
_machine_uuid = None

def set_machine_uuid(uuid):
    global _machine_uuid
    _machine_uuid = uuid


_REGISTRY_KEY = r"SOFTWARE\AgenteBacar"
_REGISTRY_VALUE = "machine_id"


def _leer_machine_id_registro() -> str | None:
    try:
        import winreg
        with winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE, _REGISTRY_KEY) as k:
            val, _ = winreg.QueryValueEx(k, _REGISTRY_VALUE)
            return val.strip() if val and val.strip() else None
    except Exception:
        return None


def _guardar_machine_id_registro(machine_id: str) -> None:
    try:
        import winreg
        with winreg.CreateKey(winreg.HKEY_LOCAL_MACHINE, _REGISTRY_KEY) as k:
            winreg.SetValueEx(k, _REGISTRY_VALUE, 0, winreg.REG_SZ, machine_id)
        log_debug(f"machine_id guardado en registro: {machine_id}")
    except Exception as e:
        log_debug(f"No se pudo guardar machine_id en registro: {e}")


def _obtener_identificador_unico_adicional() -> str:
    """Obtiene un identificador único (MachineGuid o MAC) para evitar colisiones con UUIDs genéricos."""
    try:
        import winreg
        with winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE, r"SOFTWARE\Microsoft\Cryptography") as k:
            val, _ = winreg.QueryValueEx(k, "MachineGuid")
            if val and val.strip():
                return val.strip().lower()
    except Exception:
        pass
    try:
        import uuid
        return f"{uuid.getnode():012x}"
    except Exception:
        import random
        return f"{random.randint(10000000, 99999999)}"

def resolver_machine_id(uuid_hardware: str, hostname: str) -> str:
    """
    Devuelve el ID definitivo de esta máquina para Firestore.
    Orden de prioridad:
      1. HKLM\\SOFTWARE\\AgenteBacar\\machine_id  (se confía siempre si existe)
      2. uuid_hardware si no hay colisión en Firestore
      3. f"{hostname}_{uuid_hardware[:8]}" si otro equipo ya usa ese UUID
    El ID resuelto se persiste en el registro para los próximos arranques.
    """
    # 1. Registro local — fuente de verdad para arranques posteriores
    id_local = _leer_machine_id_registro()
    if id_local:
        try:
            doc = db.collection(FIREBASE_COLLECTION_NAME).document(id_local).get()
            if doc.exists:
                hostname_existente = (doc.to_dict() or {}).get("hostname", "")
                if hostname_existente and hostname_existente.lower() != hostname.lower():
                    log_debug(
                        f"resolver_machine_id: ID del registro ({id_local}) pertenece a "
                        f"'{hostname_existente}', no a '{hostname}'. Re-evaluando colisión."
                    )
                    id_local = None
        except Exception as e:
            log_debug(f"resolver_machine_id: error validando ID del registro ({e}). Usando registro.")

    if id_local:
        log_debug(f"resolver_machine_id: ID del registro → {id_local}")
        return id_local

    # 2. Primera vez — verificar colisión en Firestore
    try:
        doc = db.collection(FIREBASE_COLLECTION_NAME).document(uuid_hardware).get()
        if doc.exists:
            hostname_existente = (doc.to_dict() or {}).get("hostname", "")
            if hostname_existente and hostname_existente.lower() != hostname.lower():
                sufijo_unico = _obtener_identificador_unico_adicional()
                id_alternativo = f"{hostname}_{sufijo_unico[:8]}".lower()
                log_debug(
                    f"resolver_machine_id: COLISION — uuid={uuid_hardware} pertenece a "
                    f"'{hostname_existente}'. Este equipo ({hostname}) usará '{id_alternativo}'"
                )
                registrar_log_actualizacion(
                    "UUID_COLISION",
                    f"UUID {uuid_hardware} ya pertenece a '{hostname_existente}'; "
                    f"este equipo ({hostname}) usará ID alternativo '{id_alternativo}'.",
                    uuid=id_alternativo,
                    hostname=hostname,
                    extra={
                        "uuid_hardware": uuid_hardware,
                        "hostname_colisionante": hostname_existente,
                        "id_alternativo": id_alternativo,
                    },
                )
                _guardar_machine_id_registro(id_alternativo)
                return id_alternativo
    except Exception as e:
        log_debug(f"resolver_machine_id: error verificando Firestore ({e}). Usando uuid_hardware.")

    # 2.5 Fallback: buscar doc existente por campo uuid_hardware + hostname
    #     Cubre reinstalaciones donde el doc tiene ID combinado (registro vacío)
    try:
        candidatos = (
            db.collection(FIREBASE_COLLECTION_NAME)
            .where("uuid_hardware", "==", uuid_hardware)
            .limit(5)
            .get()
        )
        for doc in candidatos:
            data = doc.to_dict() or {}
            if data.get("hostname", "").lower() == hostname.lower():
                id_recuperado = doc.id
                sufijo_actual = _obtener_identificador_unico_adicional()[:8]
                # Evitar robar el ID de otra máquina en caso de UUID genérico + mismo hostname
                if "_" in id_recuperado and sufijo_actual not in id_recuperado:
                    continue
                
                log_debug(
                    f"resolver_machine_id: doc recuperado por uuid_hardware "
                    f"→ {id_recuperado}"
                )
                _guardar_machine_id_registro(id_recuperado)
                return id_recuperado
    except Exception as e:
        log_debug(f"resolver_machine_id: error en búsqueda por uuid_hardware ({e}).")

    # Sin colisión — usar UUID de hardware
    _guardar_machine_id_registro(uuid_hardware)
    log_debug(f"resolver_machine_id: sin colisión → {uuid_hardware}")
    return uuid_hardware


def log_centralizado(level, category, message, exception=None):
    """Escribe un log a la colección centralizada cyberwatch_logs (dashboard)."""
    try:
        doc = {
            "timestamp": firestore.SERVER_TIMESTAMP,
            "level": level,
            "service": "AgenteBacar",
            "machineId": _machine_uuid or "",
            "hostname": _obtener_hostname(),
            "category": category,
            "message": message,
        }
        if exception:
            doc["exception"] = str(exception)
        db.collection("cyberwatch_logs").add(doc)
    except:
        pass


_LOG_ACTUALIZACIONES_PATH = (
    "C:\\agente_actualizaciones.jsonl" if os.path.exists("C:\\") else "agente_actualizaciones.jsonl"
)

# Creado por el .bat de auto_update tras copy exitoso; el próximo arranque del .exe lo borra y loguea REEMPLAZO_COMPLETADO.
FLAG_POST_AGENT_UPDATE = "_agente_hw_post_update.flag"


def _ruta_flag_post_actualizacion():
    if not getattr(sys, "frozen", False):
        return None
    return os.path.join(os.path.dirname(sys.executable), FLAG_POST_AGENT_UPDATE)


def _sanear_contexto(ctx, max_str=900):
    """Valores listos para JSON/Firestore (strings acotados, sin None)."""
    if not ctx:
        return None
    out = {}
    for k, v in ctx.items():
        if v is None:
            continue
        if isinstance(v, (int, float, bool)):
            out[str(k)] = v
        elif isinstance(v, dict):
            anidado = _sanear_contexto(v, max_str=min(max_str, 400))
            if anidado:
                out[str(k)] = anidado
        else:
            s = str(v)
            out[str(k)] = s if len(s) <= max_str else s[: max_str - 3] + "..."
    return out or None


def registrar_log_actualizacion(evento, detalle="", uuid=None, hostname=None, extra=None):
    """
    Guarda un evento del proceso de actualización del agente:
      - Localmente en agente_actualizaciones.jsonl (JSON Lines)
      - En Firestore colección 'logs_actualizaciones'
    extra: dict con datos estructurados (HTTP, rutas, hash, etc.) → campo "contexto".
    """
    ts_str = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
    entrada = {
        "timestamp": ts_str,
        "evento": evento,
        "detalle": detalle,
        "uuid": uuid or "",
        "hostname": hostname or _obtener_hostname(),
        "version_agente": VERSION_AGENTE or "?",
    }
    ctx = _sanear_contexto(extra)
    if ctx:
        entrada["contexto"] = ctx

    # --- Log local ---
    try:
        with open(_LOG_ACTUALIZACIONES_PATH, "a", encoding="utf-8") as f:
            f.write(json.dumps(entrada, ensure_ascii=False) + "\n")
    except Exception as e:
        log_debug(f"Error escribiendo log local: {e}")

    # --- Log en Firestore ---
    try:
        doc_data = {**entrada, "timestamp": firestore.SERVER_TIMESTAMP}
        ref = db.collection("logs_actualizaciones").add(doc_data)
        if isinstance(ref, tuple):
            ref = ref[-1]
        rid = getattr(ref, "id", None) or str(ref)
        log_debug(f"logs_actualizaciones OK evento={evento} doc={rid}")
    except Exception as e:
        log_debug(f"Error escribiendo log en Firestore (evento={evento}): {e}")

# Importación robusta de configuración
_cfg_version = None
try:
    import config.config as cfg
    FIREBASE_JSON_PATH = cfg.FIREBASE_JSON_PATH
    FIREBASE_COLLECTION_NAME = cfg.FIREBASE_COLLECTION_NAME
    _cfg_version = getattr(cfg, "VERSION", None)
except Exception:
    base = getattr(sys, "_MEIPASS", os.path.dirname(os.path.abspath(__file__)))
    FIREBASE_JSON_PATH = os.path.join(base, "auth", "serviceAccountKey.json")
    FIREBASE_COLLECTION_NAME = "computadoras"
    _cfg_version = None


def _version_desde_exe_o_config():
    """En .exe empaquetado, prioriza la versión del PE (Propiedades del archivo); evita drift con config embebido."""
    if sys.platform == "win32" and getattr(sys, "frozen", False):
        try:
            from src.core.exe_version import pe_file_version_string

            v = pe_file_version_string(sys.executable)
            if v:
                return v
        except Exception:
            pass
    return _cfg_version


VERSION_AGENTE = _version_desde_exe_o_config()


def _project_id_desde_service_account_json(path: str) -> str:
    """project_id embebido en el JSON de la cuenta de servicio (sin red)."""
    try:
        with open(path, encoding="utf-8") as f:
            data = json.load(f)
        pid = (data.get("project_id") or "").strip()
        return pid or "?"
    except Exception as e:
        return f"?(error leyendo JSON: {e})"


def _probar_rpc_firestore() -> None:
    """
    initialize_app() no hace llamadas a Firestore: el mensaje 'credenciales OK' no implica DB alcanzable.
    Forzamos una lectura mínima para validar gRPC/TLS hacia Google (distinto del urllib del firewall).
    """
    pid = _project_id_desde_service_account_json(FIREBASE_JSON_PATH)
    log_debug(
        f"Firestore: comprobando RPC — proyecto_id={pid}, coleccion={FIREBASE_COLLECTION_NAME}"
    )
    try:
        q = db.collection(FIREBASE_COLLECTION_NAME).limit(1)
        try:
            q.get(timeout=25.0)
        except TypeError:
            q.get()
        log_debug("Firestore RPC OK — la base respondió (lectura mínima en computadoras)")
    except Exception as e:
        log_debug(
            f"Firestore RPC FALLÓ — {type(e).__name__}: {e} "
            "(revisá firewall/proxy, API Cloud Firestore habilitada y JSON del proyecto correcto)"
        )


# Inicialización única
if not firebase_admin._apps:
    try:
        # ── Detección de modo emulador ──────────────────────────────────────
        # El Admin SDK usa FIRESTORE_EMULATOR_HOST automáticamente para
        # redirigir todas las llamadas al emulador local (no toca producción).
        # Cuando esa variable está presente, saltamos los chequeos de red real.
        _emulator_host = os.environ.get("FIRESTORE_EMULATOR_HOST", "").strip()
        _usando_emulador = bool(_emulator_host)

        if _usando_emulador:
            log_debug(
                f"⚠️  MODO EMULADOR ACTIVO — Firestore apunta a {_emulator_host}. "
                "La base de datos de producción NO será afectada."
            )
        else:
            _verificar_y_reparar_conectividad()

        if not os.path.exists(FIREBASE_JSON_PATH):
            log_debug(f"ERROR: No existe el JSON en {FIREBASE_JSON_PATH}")
        cred = credentials.Certificate(FIREBASE_JSON_PATH)
        firebase_admin.initialize_app(cred)

        if _usando_emulador:
            log_debug(f"Firebase Admin SDK inicializado → EMULADOR ({_emulator_host})")
        else:
            log_debug(
                "Firebase Admin inicializado (credenciales cargadas; la conexión real a Firestore se prueba justo después)"
            )
    except Exception as e:
        log_debug(f"Fallo crítico de conexión: {str(e)}")
        sys.exit(1)

db = firestore.client()

_emulator_host_init = os.environ.get("FIRESTORE_EMULATOR_HOST", "").strip()
if not _emulator_host_init:
    _probar_rpc_firestore()

def fallo_actualizacion_agente_remota(uuid_pc, hostname, evento, detalle, contexto=None):
    """
    Tras ACTUALIZACION_PROGRAMADA: si falla descarga/reemplazo, deja trazas claras y
    actualiza tareas/{uuid} a ACTUALIZAR_AGENTE_ERROR con fase + contexto.
    """
    hn = hostname or _obtener_hostname()
    registrar_log_actualizacion(evento, detalle, uuid=uuid_pc, hostname=hn, extra=contexto)
    if not uuid_pc:
        return
    resultado = {
        "estado": "error",
        "fase": evento,
        "mensaje": (detalle or "")[:2000],
    }
    ctx = _sanear_contexto(contexto, max_str=500)
    if ctx:
        resultado["contexto"] = ctx
    try:
        db.collection("tareas").document(uuid_pc).update(
            {
                "comando": "ACTUALIZAR_AGENTE_ERROR",
                "resultado_updates": resultado,
                "fecha_comando_ejecutado": firestore.SERVER_TIMESTAMP,
            }
        )
    except Exception as e:
        log_debug(f"fallo_actualizacion_agente_remota (update tareas): {e}")


def reportar_post_actualizacion_agente_si_aplica(uuid_pc):
    """
    Tras ACTUALIZAR_AGENTE el proceso termina y el .bat no puede escribir en Firestore.
    Si el batch copió el exe bien, deja un flag junto al .exe; al arrancar de nuevo
    registramos REEMPLAZO_COMPLETADO en logs_actualizaciones.
    """
    if not uuid_pc:
        return
    path = _ruta_flag_post_actualizacion()
    if not path or not os.path.isfile(path):
        return
    try:
        os.remove(path)
    except OSError:
        pass
    exe = sys.executable if getattr(sys, "frozen", False) else ""
    registrar_log_actualizacion(
        "REEMPLAZO_COMPLETADO",
        "Servicio en marcha tras ACTUALIZAR_AGENTE: el .bat reemplazó el .exe y reinició el servicio; este arranque ya corre el nuevo binario.",
        uuid=uuid_pc,
        hostname=_obtener_hostname(),
        extra={
            "ruta_exe": exe,
            "version_en_ejecucion": VERSION_AGENTE or "?",
            "flag_post_update": FLAG_POST_AGENT_UPDATE,
        },
    )


# ==================== SISTEMA DE CONTADORES ====================
_contadores = {
    'sincronizaciones_totales': 0,
    'ultima_sync_completa': 0,
    'ultima_sync_apps': 0,
    'ultima_sync_errores': 0,
    'ultima_sync_perifericos': 0,
    'ultima_sync_updates': 0,
    'ultima_sync_software': 0,
    'ultima_sync_programas': 0
}

_hashes_memoria = {}

def _error_es_documento_inexistente(err):
    """True si Firestore rechazó update porque no existe el documento (p. ej. borrado en consola o falló el primer set)."""
    if isinstance(err, google_api_exceptions.NotFound):
        return True
    try:
        import grpc
        if isinstance(err, grpc.RpcError) and err.code() == grpc.StatusCode.NOT_FOUND:
            return True
    except (ImportError, AttributeError):
        pass
    msg = str(err).lower()
    return "no document to update" in msg or (
        "404" in msg and "document" in msg
    )


def _es_error_transitorio(err):
    """True si es un error de red/Firebase transitorio (503, 504, red no disponible)."""
    if isinstance(err, (google_api_exceptions.ServiceUnavailable,
                        google_api_exceptions.DeadlineExceeded)):
        return True
    try:
        import grpc
        if isinstance(err, grpc.RpcError):
            return err.code() in (grpc.StatusCode.UNAVAILABLE, grpc.StatusCode.DEADLINE_EXCEEDED)
    except (ImportError, AttributeError):
        pass
    msg = str(err).lower()
    return (
        "503" in msg or "504" in msg
        or "unavailable" in msg
        or "deadline exceeded" in msg
        or "network is unreachable" in msg
        or "wsagetoverlappedresult" in msg
    )


def _ejecutar_con_reintento(fn, max_intentos=3, esperas=(5, 15, 30)):
    """Ejecuta fn() reintentando ante errores transitorios de red/Firebase."""
    for intento in range(max_intentos):
        try:
            return fn()
        except Exception as e:
            if not _es_error_transitorio(e) or intento == max_intentos - 1:
                raise
            espera = esperas[min(intento, len(esperas) - 1)]
            log_debug(f"Error transitorio (intento {intento + 1}/{max_intentos}), reintentando en {espera}s: {e}")
            time.sleep(espera)


def _obtener_hash(dato):
    """Calcula un hash MD5 de un diccionario/lista para detectar cambios y evitar escrituras innecesarias."""
    try:
        return hashlib.md5(json.dumps(dato, sort_keys=True, default=str).encode('utf-8')).hexdigest()
    except Exception:
        return None


def sincronizar_programas_instalados(uuid_pc, programas):
    """
    Escribe la lista en la subcolección computadoras/{uuid}/programas/{slug}.
    - Un doc por programa; el slug se deriva del nombre, así que un upgrade de versión sobrescribe el mismo doc.
    - Borra docs huérfanos (programas desinstalados desde el último sync).
    """
    if not uuid_pc or programas is None:
        return
    try:
        from src.core.programas_instalados import slug_programa
    except Exception as e:
        log_debug(f"sincronizar_programas_instalados: import falló: {e}")
        return
    try:
        sub_ref = (
            db.collection(FIREBASE_COLLECTION_NAME)
            .document(uuid_pc)
            .collection("programas")
        )
        slugs_actuales = set()
        batch = db.batch()
        ops = 0
        for p in programas:
            nombre = (p.get("nombre") or "").strip()
            slug = slug_programa(nombre)
            if not slug:
                continue
            slugs_actuales.add(slug)
            doc_data = {
                "nombre": nombre,
                "version": p.get("version") or "",
                "publisher": p.get("publisher") or "",
                "fecha_instalacion": p.get("fecha_instalacion") or "",
                "arquitectura": p.get("arquitectura") or "",
                "ultima_vez_visto": firestore.SERVER_TIMESTAMP,
            }
            batch.set(sub_ref.document(slug), doc_data)
            ops += 1
            if ops >= 400:
                batch.commit()
                batch = db.batch()
                ops = 0

        for doc in sub_ref.stream():
            if doc.id not in slugs_actuales:
                batch.delete(doc.reference)
                ops += 1
                if ops >= 400:
                    batch.commit()
                    batch = db.batch()
                    ops = 0

        if ops > 0:
            batch.commit()
        log_debug(
            f"Programas sync OK: {len(slugs_actuales)} programas para {uuid_pc}"
        )
    except Exception as e:
        log_debug(f"Error sincronizando programas instalados: {e}")

def enviar_datos_pc(datos, forzar_completo=False):
    """
    Envía datos con sistema de frecuencias diferenciadas.
    
    - Datos básicos (CPU, RAM, disco): cada 5 min (siempre)
    - Aplicaciones activas: cada 15 min
    - Errores del sistema: cada 30 min
    - IP pública/AnyDesk: solo en sync completa inicial
    """
    try:
        document_id = datos.get("uuid")
        if not document_id:
            return
        
        tiempo_actual = time.time()

        # programas_instalados va a subcolección, nunca al doc principal
        programas = datos.pop("programas_instalados", None)

        # Primera sincronización o forzada → COMPLETA
        # El contador se incrementa DESPUÉS del set() exitoso; si falla, la próxima
        # llamada también usará set() en lugar de update(), evitando 404.
        if _contadores['sincronizaciones_totales'] == 0 or forzar_completo:
            datos["ultima_sincronizacion"] = firestore.SERVER_TIMESTAMP
            datos["version_agente"] = VERSION_AGENTE or "?"
            datos["estado_conexion"] = "ONLINE"
            _ejecutar_con_reintento(
                lambda: db.collection(FIREBASE_COLLECTION_NAME).document(document_id).set(datos, merge=True)
            )
            _contadores['sincronizaciones_totales'] += 1
            _contadores['ultima_sync_completa'] = tiempo_actual
            _contadores['ultima_sync_apps'] = tiempo_actual
            _contadores['ultima_sync_errores'] = tiempo_actual
            if programas is not None:
                sincronizar_programas_instalados(document_id, programas)
                _contadores['ultima_sync_programas'] = tiempo_actual
            _contadores['ultima_sync_perifericos'] = tiempo_actual
            _contadores['ultima_sync_updates'] = tiempo_actual
            _contadores['ultima_sync_software'] = tiempo_actual

            # Guardar hashes iniciales (solo sync completa)
            for key in ["aplicaciones_activas", "errores_recientes", "perifericos", "windows_updates", "software_critico"]:
                if key in datos:
                    _hashes_memoria[key] = _obtener_hash(datos[key])

            log_debug(f"Sincronización COMPLETA: {document_id}")
            log_centralizado("Info", "Sync", f"Sincronización COMPLETA: {document_id}")
            return

        # Sincronizaciones posteriores → INCREMENTALES
        _contadores['sincronizaciones_totales'] += 1
        actualizacion = {
            "cpu_uso_porcentaje": datos.get("cpu_uso_porcentaje"),
            "ram_uso_porcentaje": datos.get("ram_uso_porcentaje"),
            "discos": datos.get("discos"),
            "red": datos.get("red"),
            "servicios_criticos": datos.get("servicios_criticos"),
            "ultima_sincronizacion": firestore.SERVER_TIMESTAMP,
            "version_agente": VERSION_AGENTE or "?",
            "estado_conexion": "ONLINE",
        }
        
        # Aplicaciones cada 15 min (900 seg)
        if tiempo_actual - _contadores['ultima_sync_apps'] >= 900:
            if "aplicaciones_activas" in datos:
                actualizacion["aplicaciones_activas"] = datos["aplicaciones_activas"]
                _contadores['ultima_sync_apps'] = tiempo_actual
                log_debug("Actualizando aplicaciones activas")
        
        # Errores cada 30 min (1800 seg)
        if tiempo_actual - _contadores['ultima_sync_errores'] >= 1800:
            if "errores_recientes" in datos:
                actualizacion["errores_recientes"] = datos["errores_recientes"]
                _contadores['ultima_sync_errores'] = tiempo_actual
                log_debug("Actualizando errores del sistema")
            if "perifericos" in datos:
                actualizacion["perifericos"] = datos["perifericos"]
                _contadores['ultima_sync_perifericos'] = tiempo_actual
                log_debug("Actualizando periféricos")

        # Windows Updates cada 30 min (1800 seg)
        if tiempo_actual - _contadores['ultima_sync_updates'] >= 1800:
            if "windows_updates" in datos:
                actualizacion["windows_updates"] = datos["windows_updates"]
                _contadores['ultima_sync_updates'] = tiempo_actual
                log_debug("Actualizando Windows Updates")

        # Software critico cada 60 min (3600 seg) — cambia poco
        if tiempo_actual - _contadores['ultima_sync_software'] >= 3600:
            if "software_critico" in datos:
                actualizacion["software_critico"] = datos["software_critico"]
                _contadores['ultima_sync_software'] = tiempo_actual
                log_debug("Actualizando software critico")

        doc_ref = db.collection(FIREBASE_COLLECTION_NAME).document(document_id)
        try:
            _ejecutar_con_reintento(lambda: doc_ref.update(actualizacion))
            log_debug(f"Sincronización incremental: {document_id}")
        except Exception as upd_err:
            if not _error_es_documento_inexistente(upd_err):
                raise
            log_debug(
                f"update sin documento ({document_id}), recuperando con set(merge=True)"
            )
            recuperacion = dict(datos)
            recuperacion.update(actualizacion)
            recuperacion["ultima_sincronizacion"] = firestore.SERVER_TIMESTAMP
            recuperacion["version_agente"] = VERSION_AGENTE or "?"
            recuperacion["estado_conexion"] = "ONLINE"
            if programas is not None:
                recuperacion["programas_instalados"] = programas
            _ejecutar_con_reintento(lambda: doc_ref.set(recuperacion, merge=True))
            if programas is not None:
                sincronizar_programas_instalados(document_id, programas)
                _contadores["ultima_sync_programas"] = tiempo_actual
            log_debug(f"Sincronización recuperada (set merge): {document_id}")

        # Programas instalados cada 60 min → subcolección computadoras/{uuid}/programas
        if (
            programas is not None
            and tiempo_actual - _contadores['ultima_sync_programas'] >= 3600
        ):
            sincronizar_programas_instalados(document_id, programas)
            _contadores['ultima_sync_programas'] = tiempo_actual

    except Exception as e:
        log_debug(f"Error enviando datos: {e}")
        log_centralizado("Error", "Sync", f"Error enviando datos: {e}", e)


def escuchar_comandos_remotos(uuid_pc, evento_actualizar=None):
    """Listener optimizado para comandos remotos. evento_actualizar: handle para ACTUALIZAR_AGENTE."""
    global _tareas_snapshot_watch
    tareas_ref = db.collection("tareas").document(uuid_pc)
    try:
        tareas_ref.set({
            "hostname": _obtener_hostname(),
            "comando": "NINGUNO",
            "ultima_conexion": firestore.SERVER_TIMESTAMP
        }, merge=True)
    except Exception as e:
        log_debug(f"Error en listener: {e}")
        return

    def on_snapshot(snapshot_arg, changes, read_time):
        """
        google-cloud-firestore llama al callback como (keys, appliedChanges, read_time)
        donde keys es una lista de DocumentSnapshot (un elemento en watch de documento).
        El código anterior asumía un solo DocumentSnapshot y fallaba con AttributeError.
        """
        from src.core.scanner import obtener_datos_pc

        try:
            doc_snapshot = snapshot_arg
            if isinstance(snapshot_arg, (list, tuple)):
                if not snapshot_arg:
                    return
                doc_snapshot = snapshot_arg[0]
            if not getattr(doc_snapshot, "exists", False):
                return
            # Ignorar entregas sin ADDED/MODIFIED (p. ej. solo metadatos). Si changes viene vacío,
            # igual procesamos el snapshot actual (algunos clientes no rellenan changes).
            if changes and not any(
                getattr(getattr(c, "type", None), "name", str(getattr(c, "type", "")))
                in ("ADDED", "MODIFIED")
                for c in changes
            ):
                return
            data = doc_snapshot.to_dict() or {}
        except Exception as e:
            log_debug(f"on_snapshot(tareas) error: {e}")
            try:
                log_centralizado("Error", "Comando", f"Listener tareas/{uuid_pc}: {e}", e)
            except Exception:
                pass
            return
        raw = data.get("comando", "")
        comando = raw.strip() if isinstance(raw, str) else str(raw)
        hn = _obtener_hostname()

        if comando == "ACTUALIZAR_DATOS":
            log_debug("Comando recibido: ACTUALIZAR_DATOS")
            log_centralizado("Info", "Comando", f"Comando recibido: ACTUALIZAR_DATOS (host {hn})")
            registrar_log_actualizacion(
                "ACTUALIZAR_DATOS",
                f"Sincronización completa solicitada (tareas/{uuid_pc}, host {hn})",
                uuid=uuid_pc,
                hostname=hn,
            )
            tareas_ref.update({"comando": "PROCESANDO..."})
            try:
                nuevos_datos = obtener_datos_pc(incluir_pesados=True)
                nuevos_datos["uuid"] = uuid_pc
                enviar_datos_pc(nuevos_datos, forzar_completo=True)
                tareas_ref.update({
                    "comando": "PROCESADO",
                    "fecha_comando_ejecutado": firestore.SERVER_TIMESTAMP
                })
                registrar_log_actualizacion(
                    "ACTUALIZAR_DATOS_OK",
                    f"Sync completa enviada a computadoras/{uuid_pc} (host {hn})",
                    uuid=uuid_pc,
                    hostname=hn,
                )
            except Exception as e:
                log_debug(f"Error comando: {e}")
                log_centralizado("Error", "Comando", f"Error en ACTUALIZAR_DATOS: {e}", e)
                registrar_log_actualizacion(
                    "ERROR",
                    f"Error en ACTUALIZAR_DATOS: {e}",
                    uuid=uuid_pc,
                    hostname=hn,
                )
                try:
                    tareas_ref.update({
                        "comando": "ACTUALIZAR_DATOS_ERROR",
                        "fecha_comando_ejecutado": firestore.SERVER_TIMESTAMP
                    })
                except Exception:
                    pass

        elif comando == "INSTALAR_UPDATES":
            log_debug("Comando recibido: INSTALAR_UPDATES")
            log_centralizado("Info", "Comando", f"Comando recibido: INSTALAR_UPDATES (host {hn})")
            registrar_log_actualizacion(
                "INSTALAR_UPDATES",
                f"Instalación de Windows Updates solicitada (host {hn})",
                uuid=uuid_pc,
                hostname=hn,
            )
            tareas_ref.update({"comando": "INSTALANDO_UPDATES..."})
            try:
                from src.core.windows_updates import instalar_updates
                resultado = instalar_updates()
                tareas_ref.update({
                    "comando": "UPDATES_PROCESADO",
                    "resultado_updates": resultado,
                    "fecha_comando_ejecutado": firestore.SERVER_TIMESTAMP
                })
                log_debug(f"Updates instalados: {resultado}")
                estado = resultado.get("estado", "?") if isinstance(resultado, dict) else str(resultado)
                registrar_log_actualizacion(
                    "INSTALAR_UPDATES_OK",
                    f"Updates instalados — estado: {estado}",
                    uuid=uuid_pc,
                    hostname=hn,
                )
                nuevos_datos = obtener_datos_pc(incluir_pesados=True)
                nuevos_datos["uuid"] = uuid_pc
                enviar_datos_pc(nuevos_datos, forzar_completo=True)
            except Exception as e:
                log_debug(f"Error instalando updates: {e}")
                log_centralizado("Error", "Comando", f"Error en INSTALAR_UPDATES: {e}", e)
                registrar_log_actualizacion(
                    "ERROR",
                    f"Error en INSTALAR_UPDATES: {e}",
                    uuid=uuid_pc,
                    hostname=hn,
                )
                tareas_ref.update({
                    "comando": "UPDATES_ERROR",
                    "resultado_updates": {"estado": "error", "mensaje": str(e)},
                    "fecha_comando_ejecutado": firestore.SERVER_TIMESTAMP
                })

        elif comando == "ACTUALIZAR_AGENTE":
            log_debug("Comando recibido: ACTUALIZAR_AGENTE")
            log_centralizado("Info", "Comando", f"Comando recibido: ACTUALIZAR_AGENTE (host {hn})")
            frozen = getattr(sys, "frozen", False)

            # --- Anti-replay: descartar comandos con más de N segundos de antigüedad ---
            try:
                from datetime import datetime, timezone
                try:
                    from config.config import UPDATE_COMMAND_MAX_AGE_SECONDS
                except Exception:
                    UPDATE_COMMAND_MAX_AGE_SECONDS = 600
                fecha_cmd = data.get("fecha_comando")
                if fecha_cmd is not None:
                    # Firestore Timestamps tienen .replace(tzinfo=...) disponible
                    if hasattr(fecha_cmd, 'replace'):
                        ts_utc = fecha_cmd.replace(tzinfo=timezone.utc) if fecha_cmd.tzinfo is None else fecha_cmd.astimezone(timezone.utc)
                    else:
                        ts_utc = None
                    if ts_utc is not None:
                        edad_seg = (datetime.now(timezone.utc) - ts_utc).total_seconds()
                        if edad_seg > UPDATE_COMMAND_MAX_AGE_SECONDS:
                            log_debug(
                                f"ACTUALIZAR_AGENTE descartado: comando con antigüedad "
                                f"{edad_seg:.0f}s > {UPDATE_COMMAND_MAX_AGE_SECONDS}s (anti-replay). "
                                f"Envía un nuevo comando desde el dashboard."
                            )
                            registrar_log_actualizacion(
                                "ACTUALIZAR_AGENTE_REPLAY_DESCARTADO",
                                f"Comando descartado por anti-replay: antigüedad {edad_seg:.0f}s > {UPDATE_COMMAND_MAX_AGE_SECONDS}s.",
                                uuid=uuid_pc,
                                hostname=hn,
                                extra={"edad_segundos": round(edad_seg), "max_permitido": UPDATE_COMMAND_MAX_AGE_SECONDS},
                            )
                            return
            except Exception as e_replay:
                log_debug(f"Anti-replay check error (no bloqueante): {e_replay}")
            # -------------------------------------------------------------------------
            registrar_log_actualizacion(
                "ACTUALIZAR_AGENTE_RECIBIDO",
                f"Listener Firestore: comando ACTUALIZAR_AGENTE para tareas/{uuid_pc} (host {hn}).",
                uuid=uuid_pc,
                hostname=hn,
                extra={
                    "modo_frozen_exe": frozen,
                    "uuid_tarea": uuid_pc,
                    "version_en_ejecucion": VERSION_AGENTE or "?",
                },
            )
            tareas_ref.update({"comando": "DESCARGANDO_AGENTE..."})
            try:
                url, cfg_meta = _leer_url_y_meta_actualizacion_agente()
                cfg_existe = bool(
                    cfg_meta.get("config_agente_hw_existe")
                    or cfg_meta.get("config_agente_legacy_existe")
                )
                if url:
                    pu = urlparse(url)
                    origen = cfg_meta.get("origen_config") or "?"
                    registrar_log_actualizacion(
                        "URL_ENCONTRADA",
                        f"URL desde config/{origen}: {pu.scheme}://{pu.netloc}{pu.path[:80]}{'…' if len(pu.path) > 80 else ''} ({len(url)} caracteres).",
                        uuid=uuid_pc,
                        hostname=hn,
                        extra={
                            "url_completa": url,
                            "url_host": pu.netloc,
                            "url_scheme": pu.scheme,
                            "url_path_preview": (pu.path or "")[:200],
                            "config_documento": origen,
                            "config_agente_hw_existe": cfg_meta.get("config_agente_hw_existe"),
                            "config_agente_legacy_existe": cfg_meta.get(
                                "config_agente_legacy_existe"
                            ),
                            "version_publicada_config": cfg_meta.get("version_publicada_config"),
                            "sha256_esperado": cfg_meta.get("sha256_esperado"),
                            "firma_esperada": cfg_meta.get("firma_esperada"),
                            "longitud_url": len(url),
                        },
                    )
                    _info_actualizacion_pendiente_list[0] = {
                        "url": url, 
                        "sha256": cfg_meta.get("sha256_esperado"),
                        "firma": cfg_meta.get("firma_esperada")
                    }
                    if evento_actualizar is not None:
                        try:
                            import win32event
                            win32event.SetEvent(evento_actualizar)
                        except Exception:
                            pass
                    tareas_ref.update({
                        "comando": "ACTUALIZACION_PROGRAMADA",
                        "fecha_comando_ejecutado": firestore.SERVER_TIMESTAMP
                    })
                    registrar_log_actualizacion(
                        "ACTUALIZACION_PROGRAMADA",
                        "Evento al hilo principal disparado: en breve DESCARGA_* → REEMPLAZO_INICIADO; tras sc start el proceso termina; REEMPLAZO_COMPLETADO solo en el próximo arranque del nuevo .exe.",
                        uuid=uuid_pc,
                        hostname=hn,
                        extra={
                            "pasos_siguientes": "GET url → validar tamaño → .bat: ping+sc stop+copy+flag+sc start",
                            "nota": "Si falla la descarga, tareas pasará a ACTUALIZAR_AGENTE_ERROR con fase y contexto.",
                        },
                    )
                else:
                    registrar_log_actualizacion(
                        "CONFIG_AGENTE_SIN_URL",
                        "Falta url en config/agente_hw (recomendado) y en config/agente (legacy). "
                        "Cargá la URL a mano en Firestore o ejecutá set_agente_url.py / workflow con actualizar Firestore.",
                        uuid=uuid_pc,
                        hostname=hn,
                        extra={
                            "config_agente_hw_existe": cfg_meta.get("config_agente_hw_existe"),
                            "config_agente_legacy_existe": cfg_meta.get(
                                "config_agente_legacy_existe"
                            ),
                            "url_leida": url or "",
                        },
                    )
                    tareas_ref.update({
                        "comando": "ACTUALIZAR_AGENTE_ERROR",
                        "resultado_updates": {
                            "estado": "error",
                            "fase": "CONFIG_AGENTE_SIN_URL",
                            "mensaje": "Falta URL en config/agente_hw o config/agente",
                            "contexto": {
                                "agente_hw_existe": cfg_meta.get("config_agente_hw_existe"),
                                "agente_legacy_existe": cfg_meta.get(
                                    "config_agente_legacy_existe"
                                ),
                            },
                        },
                        "fecha_comando_ejecutado": firestore.SERVER_TIMESTAMP
                    })
            except Exception as e:
                log_debug(f"Error ACTUALIZAR_AGENTE: {e}")
                log_centralizado("Error", "Comando", f"Excepción en ACTUALIZAR_AGENTE: {e}", e)
                registrar_log_actualizacion(
                    "ACTUALIZAR_AGENTE_EXCEPCION",
                    f"Excepción al leer config/agente_hw|agente o actualizar tareas: {e!s}",
                    uuid=uuid_pc,
                    hostname=hn,
                    extra={"tipo_excepcion": type(e).__name__},
                )
                tareas_ref.update({
                    "comando": "ACTUALIZAR_AGENTE_ERROR",
                    "resultado_updates": {
                        "estado": "error",
                        "fase": "ACTUALIZAR_AGENTE_EXCEPCION",
                        "mensaje": str(e)[:2000],
                        "contexto": {"tipo_excepcion": type(e).__name__},
                    },
                    "fecha_comando_ejecutado": firestore.SERVER_TIMESTAMP
                })

        elif comando == "RESETEAR_ID":
            log_debug("Comando recibido: RESETEAR_ID")
            log_centralizado("Info", "Comando", f"Comando recibido: RESETEAR_ID (host {hn})")
            registrar_log_actualizacion(
                "RESETEAR_ID",
                f"Reinicio de ID solicitado (host {hn}). Se borrará el registro y se reiniciará el servicio.",
                uuid=uuid_pc,
                hostname=hn,
            )
            tareas_ref.update({"comando": "RESETEANDO_ID..."})
            
            try:
                import winreg
                with winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE, _REGISTRY_KEY, 0, winreg.KEY_ALL_ACCESS) as k:
                    winreg.DeleteValue(k, _REGISTRY_VALUE)
                log_debug("machine_id borrado del registro exitosamente.")
            except Exception as e:
                log_debug(f"Aviso al borrar registro (puede no existir): {e}")

            import tempfile
            import subprocess
            bat_lines = [
                "@echo off",
                "ping 127.0.0.1 -n 4 > nul",
                'sc stop "AgenteMonitoreo" >nul 2>&1',
                "ping 127.0.0.1 -n 4 > nul",
                'sc start "AgenteMonitoreo" >nul 2>&1',
                '(goto) 2>nul & del "%~f0"'
            ]
            bat_content = "\r\n".join(bat_lines)
            try:
                fd, bat_path = tempfile.mkstemp(suffix=".bat", prefix="agente_reset_", text=True)
                os.write(fd, bat_content.encode("utf-8"))
                os.close(fd)
                
                DETACHED_PROCESS = 0x00000008
                CREATE_NO_WINDOW = 0x08000000
                subprocess.Popen(
                    ["cmd", "/c", bat_path],
                    creationflags=DETACHED_PROCESS | CREATE_NO_WINDOW,
                    close_fds=True,
                    cwd=os.path.dirname(bat_path),
                )
                tareas_ref.update({
                    "comando": "RESET_PROGRAMADO",
                    "fecha_comando_ejecutado": firestore.SERVER_TIMESTAMP
                })
            except Exception as e:
                log_debug(f"Error programando reinicio: {e}")
                tareas_ref.update({
                    "comando": "RESETEAR_ID_ERROR",
                    "resultado_updates": {"estado": "error", "mensaje": str(e)},
                    "fecha_comando_ejecutado": firestore.SERVER_TIMESTAMP
                })

    _tareas_snapshot_watch = tareas_ref.on_snapshot(on_snapshot)


def _doc_to_dict(doc):
    """Convierte un documento Firestore a dict JSON-serializable (timestamps -> ISO string)."""
    if doc is None or not getattr(doc, "exists", False):
        return None
    d = doc.to_dict()
    if not d:
        return d
    from datetime import datetime
    out = {}
    for k, v in d.items():
        if hasattr(v, "isoformat"):  # datetime / date
            out[k] = v.isoformat() if hasattr(v, "isoformat") else str(v)
        elif hasattr(v, "timestamp"):  # Firestore SERVER_TIMESTAMP result
            try:
                out[k] = datetime.utcfromtimestamp(v.timestamp()).isoformat() + "Z"
            except Exception:
                out[k] = str(v)
        else:
            out[k] = v
    return out


def exportar_estado_firestore():
    """
    Lee las colecciones usadas por este proyecto (computadoras, tareas, config)
    y devuelve un dict listo para JSON. Útil para depuración o para compartir
    el estado de la base con el asistente.
    """
    estado = {
        "computadoras": {},
        "tareas": {},
        "config": {},
        "_exportado_en": time.strftime("%Y-%m-%d %H:%M:%S UTC", time.gmtime()),
    }
    try:
        for doc in db.collection(FIREBASE_COLLECTION_NAME).stream():
            estado["computadoras"][doc.id] = _doc_to_dict(doc)
        for doc in db.collection("tareas").stream():
            estado["tareas"][doc.id] = _doc_to_dict(doc)
        for doc in db.collection("config").stream():
            estado["config"][doc.id] = _doc_to_dict(doc)
    except Exception as e:
        estado["_error"] = str(e)
    return estado


def configurar_url_actualizacion_agente(url, version=None, sha256=None, firma=None):
    """
    Escribe config/agente_hw (AgenteBacar): url obligatoria, version opcional (informativa en consola).
    Duplica url en config/agente para compatibilidad con despliegues que solo lean el doc legacy.
    """
    url = (url or "").strip()
    if not url:
        raise ValueError("La URL no puede estar vacía")
    data_hw = {"url": url}
    if version is not None:
        v = str(version).strip().lstrip("v")
        if v:
            data_hw["version"] = v
    if sha256 is not None:
        s = str(sha256).strip().lower()
        if s:
            data_hw["sha256"] = s
    if firma is not None:
        f = str(firma).strip()
        if f:
            data_hw["firma"] = f
    db.collection("config").document(CONFIG_DOC_AGENTE_HW).set(data_hw, merge=True)
    db.collection("config").document(CONFIG_DOC_AGENTE_LEGACY).set({"url": url}, merge=True)
    log_debug(
        f"Config/{CONFIG_DOC_AGENTE_HW} (+ legacy agente) url={url[:50]}..."
        + (f" version={data_hw.get('version')}" if data_hw.get("version") else "")
    )