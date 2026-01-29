import firebase_admin
from firebase_admin import credentials, firestore

# USA LA RUTA REAL A TU JSON
cred = credentials.Certificate("auth/serviceAccountKey.json")
firebase_admin.initialize_app(cred)
db = firestore.client()

print("Intentando crear colección 'tareas' por la fuerza...")
try:
    # Esta línea DEBE crear la colección
    db.collection("tareas").document("ID_DE_PRUEBA").set({
        "mensaje": "Si ves esto, funciona",
        "estado": "OK"
    })
    print("✅ ¡ÉXITO! Revisa tu navegador ahora.")
except Exception as e:
    print(f"❌ ERROR: {e}")