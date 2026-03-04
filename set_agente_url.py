#!/usr/bin/env python3
"""
Configura la URL de actualización del agente en Firebase (documento config/agente).

Uso:
  python set_agente_url.py "https://tu-servidor.com/AgenteBacar.exe"
  python set_agente_url.py --github usuario/repo v2.0.0
  python set_agente_url.py -g usuario/repo v2.0.0

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
        print("  python set_agente_url.py --github usuario/repo v2.0.0")
        return 1

    url = None
    if sys.argv[1].strip() in ("--github", "-g"):
        if len(sys.argv) < 4:
            print("Con --github hace falta: usuario/repo y el tag (ej. v2.0.0)")
            print("  python set_agente_url.py --github usuario/repo v2.0.0")
            return 1
        repo = sys.argv[2].strip()
        tag = sys.argv[3].strip()
        url = f"https://github.com/{repo}/releases/download/{tag}/AgenteBacar.exe"
        print("URL generada:", url)
    else:
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
