#!/usr/bin/env python3
"""
Limpia entradas fantasma de Firestore y fuerza sync completa en PCs activas.

1. Envía ACTUALIZAR_DATOS a las PCs activas (fuerza sync completa).
2. Borra los documentos fantasma (sin version_agente) de 'computadoras' y 'tareas'.

La colección 'config' no se toca.

Uso: python limpiar_y_sincronizar.py
"""
import os
import sys

RAIZ = os.path.dirname(os.path.abspath(__file__))
os.chdir(RAIZ)
if RAIZ not in sys.path:
    sys.path.insert(0, RAIZ)

def main():
    try:
        from firebase_admin import firestore
        from src.database.firebase_client import db, FIREBASE_COLLECTION_NAME
    except Exception as e:
        print("Error importando Firebase:", e)
        return 1

    # --- 1. Clasificar documentos ---
    activos = {}
    fantasmas = set()

    for doc in db.collection(FIREBASE_COLLECTION_NAME).stream():
        d = doc.to_dict() or {}
        version = d.get("version_agente")
        if not version or version == "-":
            fantasmas.add(doc.id)
        else:
            activos[doc.id] = d.get("hostname", "?")

    for doc in db.collection("tareas").stream():
        if doc.id not in activos:
            fantasmas.add(doc.id)

    # --- 2. Forzar sync completa en PCs activas ---
    print(f"Enviando ACTUALIZAR_DATOS a {len(activos)} PC(s) activas:")
    for uuid, hostname in activos.items():
        try:
            db.collection("tareas").document(uuid).set({
                "comando": "ACTUALIZAR_DATOS",
                "ultima_conexion": firestore.SERVER_TIMESTAMP,
            }, merge=True)
            print(f"  OK: {hostname} ({uuid})")
        except Exception as e:
            print(f"  Error {hostname}: {e}")

    # --- 3. Borrar fantasmas ---
    print(f"\nBorrando {len(fantasmas)} entradas fantasma:")
    for uuid in fantasmas:
        try:
            db.collection(FIREBASE_COLLECTION_NAME).document(uuid).delete()
            db.collection("tareas").document(uuid).delete()
            print(f"  Borrado: {uuid}")
        except Exception as e:
            print(f"  Error borrando {uuid}: {e}")

    print("\nListo. Las PCs activas van a enviar todos sus datos en los próximos segundos.")
    return 0

if __name__ == "__main__":
    sys.exit(main())
