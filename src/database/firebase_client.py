import firebase_admin
from firebase_admin import credentials, firestore
import os
import platform
import time
import sys
import json

# Para ACTUALIZAR_AGENTE: el listener escribe aquí la URL y despierta al bucle
_url_actualizacion_pendiente_list = [None]


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
            "service": "MiniAgente",
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


def registrar_log_actualizacion(evento, detalle="", uuid=None, hostname=None):
    """
    Guarda un evento del proceso de actualización del agente:
      - Localmente en agente_actualizaciones.jsonl (JSON Lines)
      - En Firestore colección 'logs_actualizaciones'
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
try:
    import config.config as cfg
    FIREBASE_JSON_PATH = cfg.FIREBASE_JSON_PATH
    FIREBASE_COLLECTION_NAME = cfg.FIREBASE_COLLECTION_NAME
    VERSION_AGENTE = getattr(cfg, "VERSION", None)
except Exception:
    base = getattr(sys, '_MEIPASS', os.path.dirname(os.path.abspath(__file__)))
    FIREBASE_JSON_PATH = os.path.join(base, "auth", "serviceAccountKey.json")
    FIREBASE_COLLECTION_NAME = "computadoras"
    VERSION_AGENTE = None

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
    registrar_log_actualizacion(
        "REEMPLAZO_COMPLETADO",
        "Servicio en marcha tras ACTUALIZAR_AGENTE: ejecutable reemplazado y servicio reiniciado por el script.",
        uuid=uuid_pc,
        hostname=_obtener_hostname(),
    )


# ==================== SISTEMA DE CONTADORES ====================
_contadores = {
    'sincronizaciones_totales': 0,
    'ultima_sync_completa': 0,
    'ultima_sync_apps': 0,
    'ultima_sync_errores': 0,
    'ultima_sync_perifericos': 0,
    'ultima_sync_updates': 0,
    'ultima_sync_software': 0
}

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
        
        # Primera sincronización o forzada → COMPLETA
        if _contadores['sincronizaciones_totales'] == 1 or forzar_completo:
            datos["ultima_sincronizacion"] = firestore.SERVER_TIMESTAMP
            datos["version_agente"] = VERSION_AGENTE or "?"
            datos["estado_conexion"] = "ONLINE"
            db.collection(FIREBASE_COLLECTION_NAME).document(document_id).set(datos)
            _contadores['ultima_sync_completa'] = tiempo_actual
            _contadores['ultima_sync_apps'] = tiempo_actual
            _contadores['ultima_sync_errores'] = tiempo_actual
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

    except Exception as e:
        log_debug(f"Error enviando datos: {e}")
        log_centralizado("Error", "Sync", f"Error enviando datos: {e}", e)


def escuchar_comandos_remotos(uuid_pc, evento_actualizar=None):
    """Listener optimizado para comandos remotos. evento_actualizar: handle para ACTUALIZAR_AGENTE."""
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

    def on_snapshot(doc_snapshot, changes, read_time):
        from src.core.scanner import obtener_datos_pc
        if not doc_snapshot.exists:
            return
        # Ignorar entregas sin ADDED/MODIFIED (p. ej. solo metadatos). Si changes viene vacío,
        # igual procesamos el snapshot actual (algunos clientes no rellenan changes).
        if changes and not any(c.type.name in ("ADDED", "MODIFIED") for c in changes):
            return
        data = doc_snapshot.to_dict() or {}
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
            registrar_log_actualizacion(
                "COMANDO_RECIBIDO",
                f"ACTUALIZAR_AGENTE recibido (host {hn}, uuid {uuid_pc})",
                uuid=uuid_pc,
                hostname=hn,
            )
            tareas_ref.update({"comando": "DESCARGANDO_AGENTE..."})
            try:
                doc_agente = db.collection("config").document("agente").get()
                url = None
                if doc_agente and doc_agente.exists:
                    cfg = doc_agente.to_dict() or {}
                    url = (cfg.get("url") or "").strip()
                if url:
                    registrar_log_actualizacion(
                        "URL_ENCONTRADA",
                        f"URL de descarga ({len(url)} caracteres): {url[:120]}",
                        uuid=uuid_pc,
                        hostname=hn,
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
                        "El hilo principal descargará el .exe y lanzará el .bat; el siguiente log en consola será REEMPLAZO_INICIADO y luego REEMPLAZO_COMPLETADO al reiniciar.",
                        uuid=uuid_pc,
                        hostname=hn,
                    )
                else:
                    registrar_log_actualizacion(
                        "ERROR",
                        "Falta config/agente con campo url en Firestore",
                        uuid=uuid_pc,
                        hostname=hn,
                    )
                    tareas_ref.update({
                        "comando": "ACTUALIZAR_AGENTE_ERROR",
                        "resultado_updates": {"estado": "error", "mensaje": "Falta config/agente con campo url"},
                        "fecha_comando_ejecutado": firestore.SERVER_TIMESTAMP
                    })
            except Exception as e:
                log_debug(f"Error ACTUALIZAR_AGENTE: {e}")
                log_centralizado("Error", "Comando", f"Excepción en ACTUALIZAR_AGENTE: {e}", e)
                registrar_log_actualizacion(
                    "ERROR",
                    f"Excepción en ACTUALIZAR_AGENTE: {e}",
                    uuid=uuid_pc,
                    hostname=hn,
                )
                tareas_ref.update({
                    "comando": "ACTUALIZAR_AGENTE_ERROR",
                    "resultado_updates": {"estado": "error", "mensaje": str(e)},
                    "fecha_comando_ejecutado": firestore.SERVER_TIMESTAMP
                })

    tareas_ref.on_snapshot(on_snapshot)


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


def configurar_url_actualizacion_agente(url):
    """
    Crea o actualiza el documento config/agente con el campo 'url'.
    Esa URL es la que usa el comando ACTUALIZAR_AGENTE para descargar la nueva versión.
    """
    url = (url or "").strip()
    if not url:
        raise ValueError("La URL no puede estar vacía")
    db.collection("config").document("agente").set({"url": url}, merge=True)
    log_debug(f"Config/agente actualizado con url: {url[:50]}...")