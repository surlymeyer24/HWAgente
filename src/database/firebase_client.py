import firebase_admin
from firebase_admin import credentials, firestore
# AGREGAMOS 'FIREBASE_COLLECTION_NAME' a la importación:
from config.config import FIREBASE_JSON_PATH, FIREBASE_COLLECTION_NAME

# 1. Verificamos si la app ya fue inicializada
if not firebase_admin._apps:
    # 2. Usamos la ruta configurada
    cred = credentials.Certificate(FIREBASE_JSON_PATH)
    firebase_admin.initialize_app(cred)

# 3. Creamos el cliente de la base de datos
db = firestore.client()

def enviar_datos_pc(datos):
    try:
        document_id = datos.get("uuid")
        
        if not document_id:
            print("❌ Error: Los datos no contienen un UUID. No se puede sincronizar.")
            return
        
        # Ahora FIREBASE_COLLECTION_NAME ya está definido gracias al import de arriba
        doc_ref = db.collection(FIREBASE_COLLECTION_NAME).document(document_id)
        
        # Creación o actualización del documento
        doc_ref.set(datos)
        
        print(f"✅ Datos sincronizados correctamente en la nube. ID: {document_id}")
    except Exception as e:
        print(f"❌ Error crítico al subir a Firebase: {e}")

if __name__ == "__main__":
    prueba = {
        "uuid": "TEST-UUID-1234",
        "hostname": "TEST-PC",
        "status": "Conectado"
    }
    enviar_datos_pc(prueba)