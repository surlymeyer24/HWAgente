#!/usr/bin/env python3
"""
scripts/importar_al_emulador.py
================================
Importa los datos del dump de produccion (firebase_dump.json) al emulador
local de Firestore.

USO:
  1. Asegurate de que el emulador este corriendo:
       firebase emulators:start --only firestore

  2. (Opcional) Actualizar el dump primero con datos frescos de produccion:
       python dump_firebase.py

  3. Importar al emulador:
       python scripts/importar_al_emulador.py

  4. Ver los datos en http://localhost:4000

Que importa:
  - computadoras/*   (todas las PCs)
  - tareas/*         (comandos pendientes)
  - config/*         (agente_hw, agente, etc.)

SEGURIDAD: el emulador esta aislado, esto NO toca produccion.
"""

import json
import os
import socket
import sys

RAIZ = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
os.chdir(RAIZ)
if RAIZ not in sys.path:
    sys.path.insert(0, RAIZ)

DUMP_PATH = os.path.join(RAIZ, "firebase_dump.json")
EMULATOR_HOST = "127.0.0.1:8080"


def _emulador_disponible():
    host, puerto = EMULATOR_HOST.split(":")
    try:
        with socket.create_connection((host, int(puerto)), timeout=2):
            return True
    except OSError:
        return False


def _limpiar_valor(v):
    """Convierte strings ISO a datetime para Firestore, deja el resto igual."""
    if isinstance(v, dict):
        return {k: _limpiar_valor(val) for k, val in v.items()}
    if isinstance(v, list):
        return [_limpiar_valor(i) for i in v]
    # Timestamps guardados como string ISO en el dump -> dejarlos como string
    # (Firestore los acepta; el emulador tambien)
    return v


def importar(db, coleccion, documentos):
    """Escribe todos los documentos de una coleccion en el emulador."""
    if not documentos:
        print(f"  {coleccion}: (vacia, nada que importar)")
        return 0

    batch = db.batch()
    ops = 0
    total = 0

    for doc_id, doc_data in documentos.items():
        if doc_data is None:
            continue
        ref = db.collection(coleccion).document(doc_id)
        batch.set(ref, _limpiar_valor(doc_data))
        ops += 1
        total += 1

        # Firestore limita batches a 500 operaciones
        if ops >= 490:
            batch.commit()
            batch = db.batch()
            ops = 0

    if ops > 0:
        batch.commit()

    return total


def main():
    print()
    print("=" * 60)
    print("  Importador: produccion -> emulador local")
    print("=" * 60)

    # 1. Verificar emulador
    if not _emulador_disponible():
        print()
        print("  [X] El emulador NO esta corriendo en", EMULATOR_HOST)
        print()
        print("  Levantalo con:")
        print("    firebase emulators:start --only firestore")
        print()
        sys.exit(1)

    print(f"\n  [OK] Emulador detectado en {EMULATOR_HOST}")

    # 2. Verificar dump
    if not os.path.isfile(DUMP_PATH):
        print(f"\n  [X] No se encontro el dump en: {DUMP_PATH}")
        print("  Generalo primero con:  python dump_firebase.py")
        sys.exit(1)

    with open(DUMP_PATH, encoding="utf-8") as f:
        dump = json.load(f)

    exportado_en = dump.get("_exportado_en", "?")
    print(f"  Dump: {os.path.basename(DUMP_PATH)}")
    print(f"  Fecha del dump: {exportado_en}")

    computadoras = dump.get("computadoras", {})
    tareas = dump.get("tareas", {})
    config_docs = dump.get("config", {})

    print(f"\n  Documentos encontrados:")
    print(f"    computadoras : {len(computadoras)}")
    print(f"    tareas       : {len(tareas)}")
    print(f"    config       : {len(config_docs)}")

    # 3. Conectar al emulador
    os.environ["FIRESTORE_EMULATOR_HOST"] = EMULATOR_HOST

    try:
        import firebase_admin
        from firebase_admin import credentials, firestore

        if not firebase_admin._apps:
            cred_path = os.path.join(RAIZ, "auth", "serviceAccountKey.json")
            cred = credentials.Certificate(cred_path)
            firebase_admin.initialize_app(cred)

        db = firestore.client()
    except Exception as e:
        print(f"\n  [X] Error conectando al emulador: {e}")
        sys.exit(1)

    # 4. Importar colecciones
    print("\n  Importando...")

    try:
        n = importar(db, "computadoras", computadoras)
        print(f"    computadoras : {n} docs escritos")

        n = importar(db, "tareas", tareas)
        print(f"    tareas       : {n} docs escritos")

        n = importar(db, "config", config_docs)
        print(f"    config       : {n} docs escritos")

    except Exception as e:
        print(f"\n  [X] Error durante la importacion: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)

    print()
    print("  [OK] Importacion completada.")
    print()
    print("  Ahora podes ver los datos en:")
    print("    http://localhost:4000  ->  Firestore")
    print()
    print("  Para probar el agente contra estos datos:")
    print("    python scripts/emulador.py")
    print()


if __name__ == "__main__":
    main()
