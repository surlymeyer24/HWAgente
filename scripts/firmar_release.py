#!/usr/bin/env python3
"""
scripts/firmar_release.py — Firma y verifica releases de AgenteBacar.

USO:
  # Generar un par de claves (solo la primera vez)
  python scripts/firmar_release.py genkey

  # Firmar un .exe antes de publicarlo
  python scripts/firmar_release.py sign dist/AgenteBacar.exe --version 5.5.0

  # Verificar que un .exe ya publicado es auténtico
  python scripts/firmar_release.py verify dist/AgenteBacar.exe <firma_base64>

SEGURIDAD:
  - La clave privada (agente_privkey.pem) NUNCA debe subirse al repositorio
    ni compartirse. Solo vive en la máquina del desarrollador.
  - La clave pública debe pegarse en auto_update.py (PUBLIC_KEY_PEM).
  - SHA-256 y firma van en Firestore → config/agente_hw.
"""

import argparse
import base64
import hashlib
import os
import sys

# ---------------------------------------------------------------------------
# Rutas por defecto
# ---------------------------------------------------------------------------
_SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
_PROJECT_ROOT = os.path.dirname(_SCRIPT_DIR)
_PRIVKEY_PATH = os.path.join(_PROJECT_ROOT, "agente_privkey.pem")
_PUBKEY_PATH  = os.path.join(_PROJECT_ROOT, "agente_pubkey.pem")


def _require_ecdsa():
    try:
        import ecdsa
        return ecdsa
    except ImportError:
        print("ERROR: Falta la librería 'ecdsa'. Instalala con:\n  pip install ecdsa")
        sys.exit(1)


# ---------------------------------------------------------------------------
# Subcomando: genkey
# ---------------------------------------------------------------------------
def cmd_genkey(args):
    ecdsa = _require_ecdsa()

    if os.path.exists(_PRIVKEY_PATH) and not args.force:
        print(f"Ya existe una clave privada en: {_PRIVKEY_PATH}")
        print("Usá --force para sobreescribirla (¡cuidado! perderás la clave anterior).")
        sys.exit(1)

    sk = ecdsa.SigningKey.generate(curve=ecdsa.NIST256p)
    vk = sk.get_verifying_key()

    with open(_PRIVKEY_PATH, "wb") as f:
        f.write(sk.to_pem())
    with open(_PUBKEY_PATH, "wb") as f:
        f.write(vk.to_pem())

    print("=" * 70)
    print("✅  Par de claves ECDSA P-256 generado exitosamente.")
    print(f"    Clave privada : {_PRIVKEY_PATH}")
    print(f"    Clave pública : {_PUBKEY_PATH}")
    print()
    print("⚠️  IMPORTANTE:")
    print("   1. Nunca subas agente_privkey.pem al repositorio.")
    print("      Agregá esta línea a .gitignore:")
    print("        agente_privkey.pem")
    print()
    print("   2. Pegá la clave pública en src/core/auto_update.py")
    print("      (reemplazá el valor de PUBLIC_KEY_PEM):")
    print()
    pub_pem = vk.to_pem().decode()
    print(f'PUBLIC_KEY_PEM = b"""{pub_pem}"""')
    print("=" * 70)


# ---------------------------------------------------------------------------
# Subcomando: sign
# ---------------------------------------------------------------------------
def cmd_sign(args):
    ecdsa = _require_ecdsa()
    exe_path = os.path.abspath(args.exe)

    if not os.path.isfile(exe_path):
        print(f"ERROR: No se encontró el archivo: {exe_path}")
        sys.exit(1)

    if not os.path.isfile(_PRIVKEY_PATH):
        print(f"ERROR: No existe la clave privada en: {_PRIVKEY_PATH}")
        print("Generá un par de claves primero con:  python scripts/firmar_release.py genkey")
        sys.exit(1)

    # Leer el .exe
    with open(exe_path, "rb") as f:
        data = f.read()

    # SHA-256
    sha256 = hashlib.sha256(data).hexdigest()

    # Firma ECDSA P-256 sobre los bytes del archivo
    with open(_PRIVKEY_PATH, "rb") as f:
        sk = ecdsa.SigningKey.from_pem(f.read())

    firma_bytes = sk.sign(data, hashfunc=hashlib.sha256)
    firma_b64   = base64.b64encode(firma_bytes).decode()

    tam_mb = len(data) / (1024 * 1024)

    print()
    print("=" * 70)
    print(f"✅  Release firmado: {os.path.basename(exe_path)}")
    print(f"    Tamaño  : {len(data):,} bytes ({tam_mb:.2f} MB)")
    print(f"    SHA-256 : {sha256}")
    print(f"    Firma   : {firma_b64}")
    print()
    print("─" * 70)
    print("📋  Pegá esto en Firestore → config/agente_hw:")
    print()
    url_placeholder = args.url or "https://objects.githubusercontent.com/.../<archivo>.exe"
    version_str = f'version: "{args.version}"' if args.version else '# version: "X.Y.Z"  (opcional, informativo)'
    print(f'  url:    "{url_placeholder}"')
    print(f'  sha256: "{sha256}"')
    print(f'  firma:  "{firma_b64}"')
    print(f'  {version_str}')
    print()
    print("─" * 70)
    print("ℹ️  Si subís el .exe a GitHub Releases, la URL tendrá este formato:")
    print("    https://objects.githubusercontent.com/<usuario>/<repo>/releases/download/<tag>/<archivo>.exe")
    print("=" * 70)
    print()

    # También guardar en un archivo de texto para comodidad
    out_path = exe_path + ".release_meta.txt"
    with open(out_path, "w", encoding="utf-8") as f:
        f.write(f"exe:    {exe_path}\n")
        f.write(f"sha256: {sha256}\n")
        f.write(f"firma:  {firma_b64}\n")
        if args.version:
            f.write(f"version: {args.version}\n")
    print(f"💾  Metadatos guardados en: {out_path}")
    print()


# ---------------------------------------------------------------------------
# Subcomando: verify
# ---------------------------------------------------------------------------
def cmd_verify(args):
    ecdsa = _require_ecdsa()
    exe_path = os.path.abspath(args.exe)

    if not os.path.isfile(exe_path):
        print(f"ERROR: No se encontró el archivo: {exe_path}")
        sys.exit(1)

    # Leer clave pública desde archivo o desde auto_update.py
    pubkey_pem = None
    if os.path.isfile(_PUBKEY_PATH):
        with open(_PUBKEY_PATH, "rb") as f:
            pubkey_pem = f.read()
    else:
        # Intentar leer desde auto_update.py
        auto_update_path = os.path.join(_PROJECT_ROOT, "src", "core", "auto_update.py")
        if os.path.isfile(auto_update_path):
            with open(auto_update_path, "r", encoding="utf-8") as f:
                content = f.read()
            import re
            m = re.search(r'PUBLIC_KEY_PEM\s*=\s*b"""(.*?)"""', content, re.DOTALL)
            if m:
                pubkey_pem = m.group(1).strip().encode()
        if not pubkey_pem:
            print(f"ERROR: No se encontró la clave pública en {_PUBKEY_PATH} ni en auto_update.py")
            sys.exit(1)

    with open(exe_path, "rb") as f:
        data = f.read()

    sha256_calculado = hashlib.sha256(data).hexdigest()

    # Verificar SHA-256 si se proporcionó
    if args.sha256:
        if sha256_calculado.lower() != args.sha256.lower():
            print(f"❌  SHA-256 NO COINCIDE")
            print(f"    Calculado : {sha256_calculado}")
            print(f"    Esperado  : {args.sha256}")
            sys.exit(1)
        print(f"✅  SHA-256 OK: {sha256_calculado}")

    # Verificar firma
    try:
        firma_bytes = base64.b64decode(args.firma)
        vk = ecdsa.VerifyingKey.from_pem(pubkey_pem)
        vk.verify(firma_bytes, data, hashfunc=hashlib.sha256)
        print(f"✅  Firma ECDSA válida para: {os.path.basename(exe_path)}")
    except Exception as e:
        print(f"❌  Firma ECDSA INVÁLIDA: {e}")
        sys.exit(1)


# ---------------------------------------------------------------------------
# Punto de entrada
# ---------------------------------------------------------------------------
def main():
    parser = argparse.ArgumentParser(
        description="Firma y verifica releases de AgenteBacar.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Ejemplos:
  python scripts/firmar_release.py genkey
  python scripts/firmar_release.py sign dist/AgenteBacar.exe --version 5.5.0
  python scripts/firmar_release.py sign dist/AgenteBacar.exe --version 5.5.0 --url https://objects.githubusercontent.com/.../AgenteBacar.exe
  python scripts/firmar_release.py verify dist/AgenteBacar.exe <firma_base64>
  python scripts/firmar_release.py verify dist/AgenteBacar.exe <firma_base64> --sha256 <hash>
""",
    )
    subparsers = parser.add_subparsers(dest="subcommand", required=True)

    # genkey
    p_genkey = subparsers.add_parser("genkey", help="Genera un nuevo par de claves ECDSA P-256.")
    p_genkey.add_argument("--force", action="store_true", help="Sobreescribir claves existentes.")
    p_genkey.set_defaults(func=cmd_genkey)

    # sign
    p_sign = subparsers.add_parser("sign", help="Firma un .exe y muestra los valores para Firestore.")
    p_sign.add_argument("exe", help="Ruta al .exe compilado (ej: dist/AgenteBacar.exe).")
    p_sign.add_argument("--version", default=None, help="Versión del agente (ej: 5.5.0).")
    p_sign.add_argument("--url", default=None, help="URL de descarga del .exe (para incluir en la salida).")
    p_sign.set_defaults(func=cmd_sign)

    # verify
    p_verify = subparsers.add_parser("verify", help="Verifica la firma ECDSA de un .exe.")
    p_verify.add_argument("exe", help="Ruta al .exe a verificar.")
    p_verify.add_argument("firma", help="Firma en base64 (de Firestore config/agente_hw.firma).")
    p_verify.add_argument("--sha256", default=None, help="SHA-256 esperado para validar también la integridad.")
    p_verify.set_defaults(func=cmd_verify)

    args = parser.parse_args()
    args.func(args)


if __name__ == "__main__":
    main()
