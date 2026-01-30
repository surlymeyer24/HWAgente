import firebase_admin
from firebase_admin import credentials, firestore
import os
import platform
import time
import sys

def log_debug(mensaje):
    try:
        # Intenta escribir en C:\ para persistencia como servicio
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
except:
    base = getattr(sys, '_MEIPASS', os.path.dirname(os.path.abspath(__file__)))
    FIREBASE_JSON_PATH = os.path.join(base, "auth", "serviceAccountKey.json")
    FIREBASE_COLLECTION_NAME = "computadoras"

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

def enviar_datos_pc(datos):
    try:
        document_id = datos.get("uuid")
        if not document_id: return
        datos["ultima_sincronizacion"] = firestore.SERVER_TIMESTAMP
        db.collection(FIREBASE_COLLECTION_NAME).document(document_id).set(datos)
        log_debug(f"Datos sincronizados: {document_id}")
    except Exception as e:
        log_debug(f"Error enviando datos: {e}")

def escuchar_comandos_remotos(uuid_pc):
    tareas_ref = db.collection("tareas").document(uuid_pc)
    try:
        tareas_ref.set({
            "hostname": platform.node(),
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
                if data and data.get('comando') == "ACTUALIZAR_DATOS":
                    log_debug("Comando recibido: ACTUALIZAR_DATOS")
                    tareas_ref.update({"comando": "PROCESANDO..."})
                    try:
                        nuevos_datos = obtener_datos_pc()
                        enviar_datos_pc(nuevos_datos)
                        tareas_ref.update({
                            "comando": "PROCESADO",
                            "fecha_comando_ejecutado": firestore.SERVER_TIMESTAMP
                        })
                    except Exception as e:
                        log_debug(f"Error comando: {e}")
    tareas_ref.on_snapshot(on_snapshot)