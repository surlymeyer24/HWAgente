import firebase_admin
from firebase_admin import credentials, firestore
import os
import platform
import time
from config.config import FIREBASE_JSON_PATH, FIREBASE_COLLECTION_NAME 

# Intentamos la importación; si falla aquí pero anda en el main, 
# la haremos de forma local dentro de la función.
try:
    from src.core.scanner import obtener_datos_pc
except ImportError:
    pass

if not firebase_admin._apps:
    cred = credentials.Certificate(FIREBASE_JSON_PATH)
    firebase_admin.initialize_app(cred)

db = firestore.client()

def enviar_datos_pc(datos):
    """Envía el inventario agregando una marca de tiempo de sincronización."""
    try:
        document_id = datos.get("uuid")
        if not document_id: return
        
        # AGREGAMOS FECHA AL INVENTARIO
        datos["ultima_sincronizacion"] = firestore.SERVER_TIMESTAMP
        
        db.collection(FIREBASE_COLLECTION_NAME).document(document_id).set(datos)
        print(f"✅ Inventario sincronizado con fecha.")
    except Exception as e:
        print(f"❌ Error inventario: {e}")

def escuchar_comandos_remotos(uuid_pc):
    tareas_ref = db.collection("tareas").document(uuid_pc)

    try:
        # REGISTRO INICIAL DE PRESENCIA
        tareas_ref.set({
            "hostname": platform.node(),
            "comando": "NINGUNO",
            "ultima_conexion": firestore.SERVER_TIMESTAMP # <--- FECHA DE LOGIN
        }, merge=True)
        print(f"✅ Documento 'tareas' listo para: {uuid_pc}")
    except Exception as e:
        print(f"❌ Error creando tarea: {e}")
        return

    def on_snapshot(doc_snapshot, changes, read_time):
        for change in changes:
            if change.type.name in ['ADDED', 'MODIFIED']:
                data = change.document.to_dict()
                comando = data.get('comando')
                
                if comando == "ACTUALIZAR_DATOS":
                    print("🔄 Pedido de actualización remota...")
                    
                    # IMPORTACIÓN LOCAL (Preventiva)
                    from src.core.scanner import obtener_datos_pc
                    
                    nuevos_datos = obtener_datos_pc()
                    
                    # AGREGAMOS LA FECHA ESPECÍFICA DE LA ORDEN
                    nuevos_datos["ultima_actualizacion_remota"] = firestore.SERVER_TIMESTAMP
                    
                    enviar_datos_pc(nuevos_datos)
                    
                    # LIMPIAMOS Y PONEMOS FECHA EN TAREAS
                    tareas_ref.update({
                        "comando": "PROCESADO",
                        "fecha_comando_ejecutado": firestore.SERVER_TIMESTAMP # <--- FECHA DE PROCESADO
                    })
                    print("✅ Actualización completada y fechas registradas en Firebase.")

    tareas_ref.on_snapshot(on_snapshot)

if __name__ == "__main__":
    uuid_test = "TEST-UUID-1234"
    enviar_datos_pc({"uuid": uuid_test, "hostname": "PC-PROBANDO"})
    escuchar_comandos_remotos(uuid_test)
    
    print("🚀 Agente activo. Probá cambiar el comando en Firebase...")
    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        pass