#!/usr/bin/env python3
"""
Script para volcar el estado de Firestore a un archivo en el proyecto.
Así puedes compartir el contenido de la base de datos (o pegar aquí) para que
el asistente pueda ver la estructura y los datos.

Requisitos:
  - Tener auth/serviceAccountKey.json en la raíz del proyecto.
  - Ejecutar desde la raíz del proyecto: python dump_firebase.py

Genera:
  - firebase_dump.json  (volcado completo)
  - firebase_dump.md    (resumen legible)
"""
import json
import os
import sys

# Ejecutar desde la raíz del proyecto
RAIZ = os.path.dirname(os.path.abspath(__file__))
os.chdir(RAIZ)
if RAIZ not in sys.path:
    sys.path.insert(0, RAIZ)

def main():
    try:
        from src.database.firebase_client import exportar_estado_firestore
    except Exception as e:
        print("Error importando Firebase (¿existe auth/serviceAccountKey.json?):", e)
        return 1

    print("Leyendo Firestore...")
    estado = exportar_estado_firestore()

    if "_error" in estado:
        print("Error leyendo Firestore:", estado["_error"])
        return 1

    # JSON completo
    json_path = os.path.join(RAIZ, "firebase_dump.json")
    with open(json_path, "w", encoding="utf-8") as f:
        json.dump(estado, f, indent=2, ensure_ascii=False)
    print("Escrito:", json_path)

    # Resumen en Markdown para leer rápido
    md_path = os.path.join(RAIZ, "firebase_dump.md")
    with open(md_path, "w", encoding="utf-8") as f:
        f.write("# Volcado Firestore - MiniAgente\n\n")
        f.write(f"Exportado: {estado.get('_exportado_en', '?')}\n\n")
        for col in ["computadoras", "tareas", "config"]:
            data = estado.get(col, {})
            f.write(f"## Colección: {col}\n\n")
            if not data:
                f.write("(vacía)\n\n")
                continue
            for doc_id, doc_data in data.items():
                f.write(f"### Documento: `{doc_id}`\n\n")
                if doc_data:
                    f.write("```json\n")
                    f.write(json.dumps(doc_data, indent=2, ensure_ascii=False))
                    f.write("\n```\n\n")
                else:
                    f.write("(sin datos)\n\n")
    print("Escrito:", md_path)
    print("\nPuedes abrir firebase_dump.md o firebase_dump.json y compartir su contenido aquí para que revise la base de datos.")
    return 0

if __name__ == "__main__":
    sys.exit(main())
