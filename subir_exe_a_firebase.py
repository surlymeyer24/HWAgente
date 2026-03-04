#!/usr/bin/env python3
"""
Sube dist/AgenteBacar.exe a Firebase Storage y muestra la URL para config/agente.

Requisitos:
  - auth/serviceAccountKey.json
  - pip install google-cloud-storage
  - En Firebase Console: Storage activado y (opcional) regla de lectura para agente/

Uso:
  python subir_exe_a_firebase.py
"""
import json
import os
import sys

RAIZ = os.path.dirname(os.path.abspath(__file__))
os.chdir(RAIZ)
EXE_PATH = os.path.join(RAIZ, "dist", "AgenteBacar.exe")
KEY_PATH = os.path.join(RAIZ, "auth", "serviceAccountKey.json")
STORAGE_PATH = "agente/AgenteBacar.exe"


def main():
    if not os.path.exists(KEY_PATH):
        print("No se encuentra auth/serviceAccountKey.json")
        return 1
    if not os.path.exists(EXE_PATH):
        print("No se encuentra dist/AgenteBacar.exe. Ejecutá antes compilar.bat")
        return 1

    try:
        from google.cloud import storage
    except ImportError:
        print("Falta el paquete. Ejecutá: pip install google-cloud-storage")
        return 1

    with open(KEY_PATH, encoding="utf-8") as f:
        key_data = json.load(f)
    project_id = key_data.get("project_id")
    if not project_id:
        print("En serviceAccountKey.json no viene project_id")
        return 1

    bucket_name = f"{project_id}.appspot.com"
    client = storage.Client.from_service_account_json(KEY_PATH)
    bucket = client.bucket(bucket_name)
    blob = bucket.blob(STORAGE_PATH)
    blob.upload_from_filename(EXE_PATH, content_type="application/octet-stream")
    # URL pública (solo funciona si en Storage Rules permitís read para agente/)
    url = f"https://firebasestorage.googleapis.com/v0/b/{bucket_name}/o/{STORAGE_PATH.replace('/', '%2F')}?alt=media"
    print("Subido a Firebase Storage:", STORAGE_PATH)
    print("URL:", url)
    print()
    print("Configurá la URL en Firebase con:")
    print(f'  python set_agente_url.py "{url}"')
    return 0


if __name__ == "__main__":
    sys.exit(main())
