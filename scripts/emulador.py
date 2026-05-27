#!/usr/bin/env python3
"""
scripts/emulador.py — Inicia el agente apuntando al emulador local de Firestore.

REQUISITOS PREVIOS (una sola vez):
  1. Tener Node.js instalado (nodejs.org)
  2. npm install -g firebase-tools
  3. firebase login        ← autenticarse con la cuenta de Google del proyecto
  4. pip install ecdsa     ← para el script de firma

PASOS DE USO:
  Ventana 1 (dejar corriendo):
    firebase emulators:start --only firestore

  Ventana 2 (arrancar el agente contra el emulador):
    python scripts/emulador.py

  Ventana 3 (opcional — probar el script de firma):
    python scripts/firmar_release.py genkey
    python scripts/firmar_release.py sign dist\\AgenteBacar.exe --version 5.5.0

CÓMO FUNCIONA:
  El Firebase Admin SDK detecta automáticamente la variable de entorno
  FIRESTORE_EMULATOR_HOST y redirige todas las lecturas/escrituras al
  emulador local. La producción NO es afectada.

  La UI del emulador corre en http://localhost:4000
  Firestore emulado corre en http://localhost:8080
"""

import os
import subprocess
import sys

# Verificar que el emulador esté levantado antes de arrancar el agente
def _emulador_disponible(host="127.0.0.1", puerto=8080, timeout=2):
    import socket
    try:
        with socket.create_connection((host, puerto), timeout=timeout):
            return True
    except OSError:
        return False


def main():
    print("=" * 65)
    print("  AgenteBacar — Modo Emulador de Firebase")
    print("=" * 65)

    # Verificar que el emulador esté corriendo
    if not _emulador_disponible():
        print()
        print("  [X] El emulador de Firestore NO esta corriendo en localhost:8080")
        print()
        print("  Levantalo en otra ventana con:")
        print("    firebase emulators:start --only firestore")
        print()
        print("  (Necesitas tener Node.js + firebase-tools instalado)")
        print("  Instalacion del CLI:  npm install -g firebase-tools")
        print("  Login:                firebase login")
        print()
        sys.exit(1)

    print()
    print("  [OK] Emulador detectado en localhost:8080")
    print("  [UI] http://localhost:4000  <-- ver datos en tiempo real")
    print()
    print("  El agente escribira en el emulador local.")
    print("  La base de datos de produccion NO sera afectada.")
    print()
    print("-" * 65)


    # Configurar el entorno para que el Admin SDK use el emulador
    env = os.environ.copy()
    env["FIRESTORE_EMULATOR_HOST"] = "127.0.0.1:8080"

    # Deshabilitar telemetría de firebase_admin hacia Google
    env["FIREBASE_ADMIN_DISABLE_METADATA_SERVICE"] = "true"

    # Arrancar el agente (en desarrollo, no como servicio de Windows)
    proyecto_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    python_exe = sys.executable

    print(f"  Ejecutando: {python_exe} main.py")
    print("-" * 65)
    print()

    try:
        subprocess.run(
            [python_exe, "main.py"],
            env=env,
            cwd=proyecto_root,
        )
    except KeyboardInterrupt:
        print()
        print("  Agente detenido por el usuario.")


if __name__ == "__main__":
    main()
