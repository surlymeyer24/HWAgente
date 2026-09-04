#!/usr/bin/env python3
"""Prueba local de auditoría de hardware sin Firebase."""

import argparse
import json
import sys
import os

# Raíz del proyecto en PYTHONPATH
_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _ROOT not in sys.path:
    sys.path.insert(0, _ROOT)

from src.core.hardware_audit import construir_snapshot_actual, detectar_cambios
from src.core.hardware_diff import cambios_a_eventos_firestore
from src.core import hardware_snapshot


def _snapshot_ejemplo_monitores():
    return {
        "version": 1,
        "monitores": [
            {
                "fingerprint": "SN:ABC123",
                "nombre": 'LG 24"',
                "numero_serie": "ABC123",
                "fabricante": "LG",
                "pulgadas": 24,
                "instance_name": "",
            },
        ],
    }


def _snapshot_monitor_agregado():
    snap = _snapshot_ejemplo_monitores()
    snap["monitores"].append({
        "fingerprint": "SN:NEW999",
        "nombre": "Samsung 27",
        "numero_serie": "NEW999",
        "fabricante": "Samsung",
        "pulgadas": 27,
        "instance_name": "",
    })
    return snap


def cmd_baseline():
    snap = _snapshot_ejemplo_monitores()
    ok = hardware_snapshot.guardar(snap)
    print("Baseline guardado:" if ok else "Error guardando baseline:", ok)
    print(json.dumps(snap, indent=2, ensure_ascii=False))


def cmd_simular_monitor_agregado():
    anterior = _snapshot_ejemplo_monitores()
    actual = _snapshot_monitor_agregado()
    cambios = detectar_cambios(anterior, actual, ("monitores",))
    eventos = cambios_a_eventos_firestore(cambios, "test-uuid", "TEST-PC", "5.5.0")
    print(f"Cambios detectados: {len(cambios)}")
    for ev in eventos:
        ev.pop("_expire_at_local", None)
        print(json.dumps(ev, indent=2, ensure_ascii=False))


def cmd_desde_pc():
    from src.core.scanner import obtener_datos_pc

    datos = obtener_datos_pc(incluir_pesados=True)
    snap = construir_snapshot_actual(datos, ("monitores", "ram", "discos", "procesador"))
    print(json.dumps(snap, indent=2, ensure_ascii=False))


def main():
    parser = argparse.ArgumentParser(description="Test local auditoría hardware")
    parser.add_argument("--baseline", action="store_true", help="Guardar snapshot baseline de ejemplo")
    parser.add_argument("--simular-monitor-agregado", action="store_true", help="Simular diff monitor agregado")
    parser.add_argument("--desde-pc", action="store_true", help="Construir snapshot desde esta PC")
    args = parser.parse_args()

    if args.baseline:
        cmd_baseline()
    elif args.simular_monitor_agregado:
        cmd_simular_monitor_agregado()
    elif args.desde_pc:
        cmd_desde_pc()
    else:
        cmd_simular_monitor_agregado()


if __name__ == "__main__":
    main()
