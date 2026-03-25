#!/usr/bin/env python3
"""
Muestra si las PCs se actualizaron: versión del agente y último comando en cada una.

Después de enviar ACTUALIZAR_AGENTE, ejecutá este script para ver:
  - version_agente: si coincide con la nueva versión, esa PC ya se actualizó.
  - último comando: ACTUALIZACION_PROGRAMADA = recibió la orden; ACTUALIZAR_AGENTE_ERROR = falló.

Uso:
  python verificar_actualizaciones.py
  python verificar_actualizaciones.py --host OFICINA01
  verificar_version.bat
  verificar_version.bat --host OFICINA01
"""
import argparse
import json
import os
import sys

RAIZ = os.path.dirname(os.path.abspath(__file__))
os.chdir(RAIZ)
if RAIZ not in sys.path:
    sys.path.insert(0, RAIZ)

def _ts_str(ts):
    if ts is None:
        return "-"
    if hasattr(ts, "isoformat"):
        return ts.isoformat()[:19].replace("T", " ")
    if hasattr(ts, "timestamp"):
        from datetime import datetime
        try:
            return datetime.utcfromtimestamp(ts.timestamp()).strftime("%Y-%m-%d %H:%M:%S")
        except Exception:
            pass
    return str(ts)[:19]

def _host_coincide(host, filtro):
    if not filtro:
        return True
    h = (host or "").lower()
    f = filtro.lower().strip()
    return f in h or h == f


def main():
    parser = argparse.ArgumentParser(
        description="Versión del agente y último comando por PC (datos en Firebase)."
    )
    parser.add_argument(
        "--host",
        metavar="TEXTO",
        help="Mostrar solo PCs cuyo hostname contiene este texto (sin distinguir mayúsculas).",
    )
    parser.add_argument(
        "--json",
        action="store_true",
        help="Salida en JSON (array compacto, útil para scripts).",
    )
    args = parser.parse_args()

    try:
        from src.database.firebase_client import db, FIREBASE_COLLECTION_NAME
    except Exception as e:
        print("Error importando Firebase:", e)
        return 1

    # Leer computadoras (hostname, version_agente)
    comps = {}
    for doc in db.collection(FIREBASE_COLLECTION_NAME).stream():
        d = doc.to_dict() or {}
        comps[doc.id] = {
            "hostname": d.get("hostname", "?"),
            "version_agente": d.get("version_agente", "-"),
        }

    # Leer tareas (último comando y fecha)
    tareas = {}
    for doc in db.collection("tareas").stream():
        d = doc.to_dict() or {}
        tareas[doc.id] = {
            "comando": d.get("comando", "?"),
            "fecha_comando": d.get("fecha_comando_ejecutado"),
            "hostname": d.get("hostname", "?"),
        }

    # Unir por UUID
    uuids = sorted(set(comps.keys()) | set(tareas.keys()))
    if not uuids:
        if args.json:
            print("[]")
        else:
            print("No hay PCs en Firebase.")
        return 0

    filas = []
    for uuid in uuids:
        c = comps.get(uuid, {})
        t = tareas.get(uuid, {})
        host = c.get("hostname") or t.get("hostname") or "?"
        if not _host_coincide(host, args.host):
            continue
        version = c.get("version_agente", "-")
        comando = t.get("comando", "-")
        fecha = t.get("fecha_comando")
        filas.append(
            {
                "uuid": uuid,
                "hostname": host,
                "version_agente": version,
                "ultimo_comando": comando,
                "fecha_comando": _ts_str(fecha),
            }
        )

    if args.json:
        print(json.dumps(filas, ensure_ascii=False))
        return 0

    if not filas:
        print("Ninguna PC coincide con --host %r." % (args.host,))
        return 0

    print("Estado de actualización por PC")
    print("-" * 70)
    for row in filas:
        print(
            f"  {row['hostname']:25}  version_agente: {row['version_agente']:8}  "
            f"último comando: {row['ultimo_comando']:25}  ({row['fecha_comando']})"
        )
    print("-" * 70)
    print()
    print("Cómo leerlo:")
    print("  - version_agente: versión que reporta esa PC (si es la nueva, ya se actualizó).")
    print("  - ACTUALIZACION_PROGRAMADA = recibió ACTUALIZAR_AGENTE y programó la actualización.")
    print("  - ACTUALIZAR_AGENTE_ERROR   = falló (revisar resultado_updates en Firestore).")
    print("  - NINGUNO = en espera o ya reinició con la nueva versión.")
    print()
    print("Si acabás de enviar actualizaciones, esperá 1-2 min y volvé a ejecutar este script.")
    return 0

if __name__ == "__main__":
    sys.exit(main())
