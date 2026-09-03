"""
Prueba local de detección de procesador (WMI + parser).
Uso: python scripts/test_cpu_local.py
     python scripts/test_cpu_local.py --sync   # incluye campos que irían a Firestore
"""
import argparse
import json
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

from src.core.scanner import _obtener_procesador_completo, obtener_datos_pc


def main():
    parser = argparse.ArgumentParser(description='Prueba detección de CPU del agente')
    parser.add_argument(
        '--sync',
        action='store_true',
        help='Muestra también procesador, nucleos_fisicos y procesador_detallado del payload de sync',
    )
    args = parser.parse_args()

    info = _obtener_procesador_completo()
    print('=== Detección WMI + parser ===')
    print(json.dumps(info, indent=2, ensure_ascii=False))

    if args.sync:
        print('\n=== Campos de sync (incluir_pesados=False) ===')
        datos = obtener_datos_pc(incluir_pesados=False)
        payload = {
            'procesador': datos.get('procesador'),
            'nucleos_fisicos': datos.get('nucleos_fisicos'),
            'procesador_detallado': datos.get('procesador_detallado'),
        }
        print(json.dumps(payload, indent=2, ensure_ascii=False))


if __name__ == '__main__':
    main()
