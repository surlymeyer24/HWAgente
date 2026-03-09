#!/usr/bin/env python3
"""
Configura la URL de actualización del agente en Firebase (documento config/agente).

Uso:
  python set_agente_url.py "https://tu-servidor.com/AgenteBacar.exe"

Requisito: auth/serviceAccountKey.json en la raíz del proyecto.
"""
import os
import sys

RAIZ = os.path.dirname(os.path.abspath(__file__))
os.chdir(RAIZ)
if RAIZ not in sys.path:
    sys.path.insert(0, RAIZ)

def main():
    if len(sys.argv) < 2:
        print("Uso:")
        print('  python set_agente_url.py "https://.../AgenteBacar.exe"')
        return 1

    url = sys.argv[1].strip()
    if not url:
        print("Error: la URL no puede estar vacía.")
        return 1

    try:
        from src.database.firebase_client import configurar_url_actualizacion_agente
    except Exception as e:
        print("Error importando Firebase (¿existe auth/serviceAccountKey.json?):", e)
        return 1

    try:
        configurar_url_actualizacion_agente(url)
        print("OK. Documento config/agente actualizado con url =", url)
        return 0
    except Exception as e:
        print("Error:", e)
        return 1

if __name__ == "__main__":
    sys.exit(main())
