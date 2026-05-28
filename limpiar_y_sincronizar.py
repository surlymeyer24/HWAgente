#!/usr/bin/env python3
import os, sys
from datetime import datetime

RAIZ = os.path.dirname(os.path.abspath(__file__))
os.chdir(RAIZ)
if RAIZ not in sys.path:
    sys.path.insert(0, RAIZ)

def parse_iso(iso_str):
    try:
        return datetime.fromisoformat(iso_str.replace("Z", "+00:00"))
    except:
        return datetime.min

def main():
    try:
        from firebase_admin import firestore
        from src.database.firebase_client import db, FIREBASE_COLLECTION_NAME
    except Exception as e:
        print("Error importando Firebase:", e)
        return 1

    por_hostname = {}
    fantasmas = set()

    # 1. Agrupar por hostname y encontrar el mas reciente
    for doc in db.collection(FIREBASE_COLLECTION_NAME).stream():
        d = doc.to_dict() or {}
        version = d.get("version_agente")
        hostname = (d.get("hostname") or "").strip()
        
        # Ignorar si no tiene version o no tiene hostname
        if not version or version == "-" or not hostname:
            fantasmas.add(doc.id)
            continue

        ts_str = str(d.get("ultima_sincronizacion") or "")
        ts = parse_iso(ts_str)
        
        if hostname not in por_hostname:
            por_hostname[hostname] = (doc.id, ts)
        else:
            # Si ya existe, nos quedamos con el mas reciente
            id_actual, ts_actual = por_hostname[hostname]
            if ts > ts_actual:
                fantasmas.add(id_actual)
                por_hostname[hostname] = (doc.id, ts)
            else:
                fantasmas.add(doc.id)

    activos = {id_doc: hostname for hostname, (id_doc, _) in por_hostname.items()}

    # 2. Agregar los que estan en tareas pero no en activos a fantasmas
    for doc in db.collection("tareas").stream():
        if doc.id not in activos:
            fantasmas.add(doc.id)

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

    print(f"\nBorrando {len(fantasmas)} entradas fantasma (duplicados o inactivos):")
    for uuid in fantasmas:
        try:
            db.collection(FIREBASE_COLLECTION_NAME).document(uuid).delete()
            db.collection("tareas").document(uuid).delete()
            print(f"  Borrado: {uuid}")
        except Exception as e:
            print(f"  Error borrando {uuid}: {e}")

    print("\nListo. PCs limpias y sin duplicados.")
    return 0

if __name__ == "__main__":
    sys.exit(main())
