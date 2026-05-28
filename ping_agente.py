import os, sys, time
from src.database.firebase_client import db
def main():
    if len(sys.argv) < 2:
        print('Uso: python ping_agente.py <UUID>')
        return
    uuid = sys.argv[1]
    ref = db.collection('tareas').document(uuid)
    print(f'Haciendo ping al agente {uuid}...')
    ref.set({'comando': 'ACTUALIZAR_DATOS'}, merge=True)
    for i in range(10):
        time.sleep(1)
        doc = ref.get().to_dict() or {}
        cmd = doc.get('comando', '')
        if cmd in ['PROCESANDO...', 'PROCESADO']:
            print('OK! El servicio ESTA CORRIENDO. Respondio al comando.')
            return
    print('ERROR: El servicio NO RESPONDE. Probablemente este detenido.')
if __name__ == '__main__':
    main()