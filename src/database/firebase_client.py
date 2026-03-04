import firebase_admin
from firebase_admin import credentials, firestore
import os
import platform
import time
import sys

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
    except Exception as e:
        log_debug(f"Fallo crítico de conexión: {str(e)}")
        sys.exit(1)

db = firestore.client()

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
            db.collection(FIREBASE_COLLECTION_NAME).document(document_id).set(datos)
            _contadores['ultima_sync_completa'] = tiempo_actual
            _contadores['ultima_sync_apps'] = tiempo_actual
            _contadores['ultima_sync_errores'] = tiempo_actual
            log_debug(f"Sincronización COMPLETA: {document_id}")
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
        for change in changes:
            if change.type.name in ['ADDED', 'MODIFIED']:
                data = change.document.to_dict()
                comando = data.get('comando', '') if data else ''

                if comando == "ACTUALIZAR_DATOS":
                    log_debug("Comando recibido: ACTUALIZAR_DATOS")
                    tareas_ref.update({"comando": "PROCESANDO..."})
                    try:
                        nuevos_datos = obtener_datos_pc(incluir_pesados=True)
                        enviar_datos_pc(nuevos_datos, forzar_completo=True)
                        tareas_ref.update({
                            "comando": "PROCESADO",
                            "fecha_comando_ejecutado": firestore.SERVER_TIMESTAMP
                        })
                    except Exception as e:
                        log_debug(f"Error comando: {e}")

                elif comando == "INSTALAR_UPDATES":
                    log_debug("Comando recibido: INSTALAR_UPDATES")
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
                        # Sync completa para reflejar el nuevo estado
                        nuevos_datos = obtener_datos_pc(incluir_pesados=True)
                        enviar_datos_pc(nuevos_datos, forzar_completo=True)
                    except Exception as e:
                        log_debug(f"Error instalando updates: {e}")
                        tareas_ref.update({
                            "comando": "UPDATES_ERROR",
                            "resultado_updates": {"estado": "error", "mensaje": str(e)},
                            "fecha_comando_ejecutado": firestore.SERVER_TIMESTAMP
                        })

                elif comando == "ACTUALIZAR_AGENTE":
                    log_debug("Comando recibido: ACTUALIZAR_AGENTE")
                    tareas_ref.update({"comando": "DESCARGANDO_AGENTE..."})
                    try:
                        doc_agente = db.collection("config").document("agente").get()
                        url = None
                        if doc_agente and doc_agente.exists:
                            data = doc_agente.to_dict() or {}
                            url = (data.get("url") or "").strip()
                        if url:
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
                        else:
                            tareas_ref.update({
                                "comando": "ACTUALIZAR_AGENTE_ERROR",
                                "resultado_updates": {"estado": "error", "mensaje": "Falta config/agente con campo url"},
                                "fecha_comando_ejecutado": firestore.SERVER_TIMESTAMP
                            })
                    except Exception as e:
                        log_debug(f"Error ACTUALIZAR_AGENTE: {e}")
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