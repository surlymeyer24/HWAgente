#!/usr/bin/env python3
"""
Configura la URL de actualización de AgenteBacar en Firebase.

Documento principal: config/agente_hw  (campos: url, version opcional)
Espejo de compatibilidad: config/agente  (solo url)

Uso:
  python set_agente_url.py "https://.../AgenteBacar.exe"
  python set_agente_url.py "https://.../AgenteBacar.exe" "2.4.0"
  python set_agente_url.py "https://.../AgenteBacar.exe" "2.4.0" "a1b2c3d4..."

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
        print('  python set_agente_url.py "https://.../AgenteBacar.exe"  [version_opcional] [sha256_opcional]')
        print("Ej.: python set_agente_url.py https://ejemplo.com/a.exe 2.4.0")
        return 1

    url = sys.argv[1].strip()
    if not url:
        print("Error: la URL no puede estar vacía.")
        return 1

    version = sys.argv[2].strip() if len(sys.argv) > 2 else None
    sha256 = sys.argv[3].strip() if len(sys.argv) > 3 else None

    try:
        from src.database.firebase_client import configurar_url_actualizacion_agente
    except Exception as e:
        print("Error importando Firebase (¿existe auth/serviceAccountKey.json?):", e)
        return 1

    try:
        configurar_url_actualizacion_agente(url, version=version, sha256=sha256)
        print("OK. config/agente_hw actualizado (y url espejada en config/agente).")
        print("  url =", url)
        if version:
            print("  version (opcional, informativa) =", version.lstrip("v"))
        if sha256:
            print("  sha256 (opcional, seguridad) =", sha256)
        return 0
    except Exception as e:
        print("Error:", e)
        return 1


if __name__ == "__main__":
    sys.exit(main())
