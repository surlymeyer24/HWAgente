import firebase_admin
from firebase_admin import credentials, firestore
from config.config import FIREBASE_JSON_PATH, FIREBASE_COLLECTION_NAME # <--- Importamos la configuración

# Inicializamos la conexión solo si no existe una previa
if not firebase_admin._apps:
    cred = credentials.Certificate(FIREBASE_JSON_PATH)
    firebase_admin.initialize_app(cred)

db = firestore.client()

def enviar_datos_pc(datos):
    try:
        document_id = datos.get("uuid")
        
        if not document_id:
            print("❌ Error: Los datos no contienen un UUID. No se puede sincronizar.")
            return
        
        # Referencia a la colección definida en config.py
        doc_ref = db.collection(FIREBASE_COLLECTION_NAME).document(document_id)
        
        # Creación o actualización del documento
        doc_ref.set(datos)
        
        print(f"✅ Datos sincronizados correctamente en la nube. ID: {document_id}")
    except Exception as e:
        print(f"❌ Error crítico al subir a Firebase: {e}")

if __name__ == "__main__":
    # Prueba rápida corregida con un UUID ficticio
    prueba = {
        "uuid": "TEST-UUID-1234",
        "hostname": "TEST-PC",
        "status": "Conectado"
    }
    enviar_datos_pc(prueba)