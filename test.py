from src.core.scanner import obtener_datos_pc
from src.database.firebase_client import enviar_datos_pc, db
import platform
from firebase_admin import firestore

try:
    datos = obtener_datos_pc()
    print(f"Datos: {datos}")
    enviar_datos_pc(datos)
    print("Envío exitoso")
    
    # Crear documento en "tareas" sin listener
    uuid_pc = datos['uuid']
    tareas_ref = db.collection("tareas").document(uuid_pc)
    tareas_ref.set({
        "hostname": platform.node(),
        "comando": "NINGUNO",
        "ultima_conexion": firestore.SERVER_TIMESTAMP
    }, merge=True)
    print("Documento en 'tareas' creado")
    
except Exception as e:
    print(f"Error: {e}")