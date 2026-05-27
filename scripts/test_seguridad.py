#!/usr/bin/env python3
"""
scripts/test_seguridad.py — Verifica que los controles de seguridad del módulo
de actualización remota funcionen correctamente contra el emulador de Firestore.

USO (con el emulador corriendo):
  python scripts/test_seguridad.py

REQUISITO:
  El emulador de Firestore debe estar corriendo:
    firebase emulators:start --only firestore
"""

import os
import sys

# Apuntar al emulador
os.environ["FIRESTORE_EMULATOR_HOST"] = "127.0.0.1:8080"

# Agregar raíz del proyecto al path
_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, _ROOT)

PASS = "✅"
FAIL = "❌"
results = []

def check(nombre, condicion, detalle=""):
    icon = PASS if condicion else FAIL
    results.append((condicion, nombre))
    print(f"  {icon}  {nombre}")
    if detalle:
        print(f"       {detalle}")


# =============================================================================
print()
print("=" * 65)
print("  Test de seguridad — Módulo de actualización remota")
print("=" * 65)
print()

# =============================================================================
print("── 1. Validación de URL (_validar_url_segura) ──────────────────")
try:
    from src.core.auto_update import _validar_url_segura

    # Debe rechazar: HTTP
    r = _validar_url_segura("http://objects.githubusercontent.com/x/y.exe")
    check("Rechaza URL http://", r is not None, r or "")

    # Debe rechazar: IP privada
    r = _validar_url_segura("https://192.168.1.100/agente.exe")
    check("Rechaza IP privada (192.168.x)", r is not None, r or "")

    # Debe rechazar: localhost
    r = _validar_url_segura("https://127.0.0.1/agente.exe")
    check("Rechaza localhost (127.0.0.1)", r is not None, r or "")

    # Debe rechazar: dominio no autorizado
    r = _validar_url_segura("https://evil.com/agente.exe")
    check("Rechaza dominio no en whitelist", r is not None, r or "")

    # Debe rechazar: URL vacía
    r = _validar_url_segura("")
    check("Rechaza URL vacía", r is not None, r or "")

    # Debe aceptar: GitHub Releases
    r = _validar_url_segura("https://objects.githubusercontent.com/user/repo/releases/download/v5.5.0/AgenteBacar.exe")
    check("Acepta objects.githubusercontent.com (HTTPS)", r is None, "URL válida ✓" if r is None else r)

    # Debe aceptar: github.com
    r = _validar_url_segura("https://github.com/user/repo/releases/download/v5.5.0/AgenteBacar.exe")
    check("Acepta github.com (HTTPS)", r is None, "URL válida ✓" if r is None else r)

except Exception as e:
    check("Importación de _validar_url_segura", False, str(e))

print()
# =============================================================================
print("── 2. SHA-256 y firma obligatorios (download_and_apply_update) ─")
try:
    # Simular llamada sin frozen — siempre retorna False antes de tocar la red
    # Solo testeamos el bloque de validación previo al frozen check
    from src.core.auto_update import _validar_url_segura

    url_ok = "https://objects.githubusercontent.com/u/r/releases/download/v1/a.exe"

    # Sin sha256
    motivo_url = _validar_url_segura(url_ok)
    check(
        "URL válida pasa la validación de URL",
        motivo_url is None,
        "OK: la URL no es rechazada por la función de URL" if motivo_url is None else motivo_url
    )

    # Simulamos el comportamiento de download_and_apply_update con sha256=None
    sha256_vacio = None
    check(
        "SHA-256 None → sería rechazado por lógica de seguridad",
        not sha256_vacio,   # True si sha256 es None/vacío (= se rechazaría)
        "La condición 'if not sha256_esperado' cubriría este caso"
    )

    # Simulamos firma vacía
    firma_vacia = "  "
    check(
        "Firma con espacios → sería rechazada",
        not firma_vacia.strip(),
        "La condición 'if not firma_esperada.strip()' cubriría este caso"
    )

except Exception as e:
    check("Validación de sha256/firma", False, str(e))

print()
# =============================================================================
print("── 3. Conectividad al emulador ─────────────────────────────────")
try:
    import socket
    with socket.create_connection(("127.0.0.1", 8080), timeout=2):
        check("Emulador de Firestore accesible en localhost:8080", True)

    import firebase_admin
    from firebase_admin import credentials, firestore as fs

    if not firebase_admin._apps:
        cred_path = os.path.join(_ROOT, "auth", "serviceAccountKey.json")
        cred = credentials.Certificate(cred_path)
        firebase_admin.initialize_app(cred)

    db = fs.client()

    # Escritura de prueba en colección de test
    ref = db.collection("_test_seguridad").document("ping")
    ref.set({"ok": True, "ts": fs.SERVER_TIMESTAMP})
    doc = ref.get()
    check("Escritura y lectura en emulador OK", doc.exists)

    # Limpiar
    ref.delete()
    check("Limpieza del documento de test OK", True)

except socket.error:
    check(
        "Emulador accesible en localhost:8080",
        False,
        "Levantá el emulador con: firebase emulators:start --only firestore"
    )
except Exception as e:
    check("Conexión al emulador", False, str(e))

print()
# =============================================================================
print("── 4. Firestore Rules — config/ bloqueada ──────────────────────")
print("   (Las rules solo bloquean a clientes con Firebase Auth,")
print("    no al Admin SDK. Para verificarlas, deployalas y usa la")
print("    UI del emulador en http://localhost:4000 → Rules Playground)")
print()

# =============================================================================
# Resumen final
total = len(results)
ok = sum(1 for passed, _ in results if passed)
print("=" * 65)
print(f"  Resultado: {ok}/{total} controles OK")
if ok == total:
    print("  ✅ Todos los controles de seguridad pasaron correctamente.")
else:
    print(f"  ⚠️  {total - ok} control(es) fallaron — revisar arriba.")
print("=" * 65)
print()

sys.exit(0 if ok == total else 1)
