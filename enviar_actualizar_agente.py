#!/usr/bin/env python3
"""
Envía el comando ACTUALIZAR_AGENTE a una o todas las PCs en Firebase.
Cada agente que esté corriendo y escuchando actualizará su .exe desde config/agente_hw.url (o config/agente.url).

Uso:
  python enviar_actualizar_agente.py              # todas las PCs
  python enviar_actualizar_agente.py UUID1 UUID2  # solo esas PCs

Requisito: auth/serviceAccountKey.json
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
        from src.database.firebase_client import db
    except Exception as e:
        print("Error importando Firebase:", e)
        return 1

    # UUIDs como argumentos, o todas leyendo desde tareas
    if len(sys.argv) > 1:
        uuids = [u.strip() for u in sys.argv[1:] if u.strip()]
        print("Enviando ACTUALIZAR_AGENTE a", len(uuids), "PC(s):")
    else:
        uuids = []
        for doc in db.collection("tareas").stream():
            uuids.append(doc.id)
        if not uuids:
            print("No hay documentos en tareas. ¿Hay PCs ya registradas?")
            return 1
        print("Enviando ACTUALIZAR_AGENTE a TODAS las PCs a la vez (" + str(len(uuids)) + " máquinas):")

    for uuid in uuids:
        try:
            db.collection("tareas").document(uuid).set({
                "comando": "ACTUALIZAR_AGENTE",
                "ultima_conexion": firestore.SERVER_TIMESTAMP,
            }, merge=True)
            print("  OK:", uuid)
        except Exception as e:
            print("  Error", uuid, ":", e)

    print("\nListo. Cada PC que tenga el agente corriendo se actualizará en los próximos segundos.")
    return 0

if __name__ == "__main__":
    sys.exit(main())
