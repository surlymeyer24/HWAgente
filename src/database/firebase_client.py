import firebase_admin
from firebase_admin import credentials, firestore
import os
import platform
import time
import sys

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

# ==================== SISTEMA DE CONTADORES ====================
_contadores = {
    'sincronizaciones_totales': 0,
    'ultima_sync_completa': 0,
    'ultima_sync_apps': 0,
    'ultima_sync_errores': 0
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
            "ultima_sincronizacion": firestore.SERVER_TIMESTAMP
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
        
        db.collection(FIREBASE_COLLECTION_NAME).document(document_id).update(actualizacion)
        log_debug(f"Sincronización incremental: {document_id}")
        
    except Exception as e:
        log_debug(f"Error enviando datos: {e}")


def escuchar_comandos_remotos(uuid_pc):
    """Listener optimizado para comandos remotos"""
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
                        # Forzar sincronización completa con todos los datos
                        nuevos_datos = obtener_datos_pc(incluir_pesados=True)
                        enviar_datos_pc(nuevos_datos, forzar_completo=True)
                        tareas_ref.update({
                            "comando": "PROCESADO",
                            "fecha_comando_ejecutado": firestore.SERVER_TIMESTAMP
                        })
                    except Exception as e:
                        log_debug(f"Error comando: {e}")
                        
    tareas_ref.on_snapshot(on_snapshot)