import firebase_admin
from firebase_admin import credentials, firestore
import json
import os
import platform
import sys
import time
from urllib.parse import urlparse

# Para ACTUALIZAR_AGENTE: el listener escribe aquí la URL y despierta al bucle
_url_actualizacion_pendiente_list = [None]

# Referencia fuerte al Watch de Firestore (si se pierde, el listener puede cortarse por GC)
_tareas_snapshot_watch = None

# Firestore: URL de actualización AgenteBacar (doc agente_hw). Legacy: config/agente solo url.
CONFIG_DOC_AGENTE_HW = "agente_hw"
CONFIG_DOC_AGENTE_LEGACY = "agente"


def _leer_url_y_meta_actualizacion_agente():
    """
    Prioridad: config/agente_hw (url + version opcional informativa),
    luego config/agente (solo url) para agentes antiguos / espejo manual.
    """
    doc_hw = db.collection("config").document(CONFIG_DOC_AGENTE_HW).get()
    doc_legacy = db.collection("config").document(CONFIG_DOC_AGENTE_LEGACY).get()
    cfg_hw = bool(doc_hw and doc_hw.exists)
    cfg_legacy = bool(doc_legacy and doc_legacy.exists)
    url = ""
    version_publicada = None
    origen = None
    if cfg_hw:
        d = doc_hw.to_dict() or {}
        url = (d.get("url") or "").strip()
        vp = (d.get("version") or "").strip()
        version_publicada = vp if vp else None
        if url:
            origen = CONFIG_DOC_AGENTE_HW
    if not url and cfg_legacy:
        d = doc_legacy.to_dict() or {}
        url = (d.get("url") or "").strip()
        if url:
            origen = CONFIG_DOC_AGENTE_LEGACY
    meta = {
        "origen_config": origen,
        "version_publicada_config": version_publicada,
        "config_agente_hw_existe": cfg_hw,
        "config_agente_legacy_existe": cfg_legacy,
    }
    return url, meta


def _url_actualizacion_pendiente():
    u = _url_actualizacion_pendiente_list[0]
    _url_actualizacion_pendiente_list[0] = None
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


# UUID de la máquina, se setea desde main.py al arrancar
_machine_uuid = None

def set_machine_uuid(uuid):
    global _machine_uuid
    _machine_uuid = uuid

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

# Inicialización única
if not firebase_admin._apps:
    try:
        if not os.path.exists(FIREBASE_JSON_PATH):
            log_debug(f"ERROR: No existe el JSON en {FIREBASE_JSON_PATH}")
        cred = credentials.Certificate(FIREBASE_JSON_PATH)
        firebase_admin.initialize_app(cred)
        log_debug("Conexión establecida con Firebase")
        # log_centralizado se llama después de que db exista (más abajo)
    except Exception as e:
        log_debug(f"Fallo crítico de conexión: {str(e)}")
        sys.exit(1)

db = firestore.client()


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
        
        _contadores['sincronizaciones_totales'] += 1
        tiempo_actual = time.time()

        # programas_instalados va a subcolección, nunca al doc principal
        programas = datos.pop("programas_instalados", None)

        # Primera sincronización o forzada → COMPLETA
        if _contadores['sincronizaciones_totales'] == 1 or forzar_completo:
            datos["ultima_sincronizacion"] = firestore.SERVER_TIMESTAMP
            datos["version_agente"] = VERSION_AGENTE or "?"
            datos["estado_conexion"] = "ONLINE"
            db.collection(FIREBASE_COLLECTION_NAME).document(document_id).set(datos)
            _contadores['ultima_sync_completa'] = tiempo_actual
            _contadores['ultima_sync_apps'] = tiempo_actual
            _contadores['ultima_sync_errores'] = tiempo_actual
            if programas is not None:
                sincronizar_programas_instalados(document_id, programas)
                _contadores['ultima_sync_programas'] = tiempo_actual
            log_debug(f"Sincronización COMPLETA: {document_id}")
            log_centralizado("Info", "Sync", f"Sincronización COMPLETA: {document_id}")
            return
        
        # Sincronizaciones posteriores → INCREMENTALES
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

        db.collection(FIREBASE_COLLECTION_NAME).document(document_id).update(actualizacion)
        log_debug(f"Sincronización incremental: {document_id}")

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
                            "longitud_url": len(url),
                        },
                    )
                    _url_actualizacion_pendiente_list[0] = url
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


def configurar_url_actualizacion_agente(url, version=None):
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
    db.collection("config").document(CONFIG_DOC_AGENTE_HW).set(data_hw, merge=True)
    db.collection("config").document(CONFIG_DOC_AGENTE_LEGACY).set({"url": url}, merge=True)
    log_debug(
        f"Config/{CONFIG_DOC_AGENTE_HW} (+ legacy agente) url={url[:50]}..."
        + (f" version={data_hw.get('version')}" if data_hw.get("version") else "")
    )