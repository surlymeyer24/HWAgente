import os
import sys
import hashlib
import base64
import ecdsa

RAIZ = os.path.dirname(os.path.abspath(__file__))
os.chdir(RAIZ)
if RAIZ not in sys.path:
    sys.path.insert(0, RAIZ)

def main():
    if len(sys.argv) < 5:
        print("Uso:")
        print('  python firmar_y_subir_update.py <URL> <version> <ruta_al_exe> <ruta_clave_privada>')
        print("Ej.: python firmar_y_subir_update.py https://ejemplo.com/Agente.exe 2.4.0 dist/AgenteBacar.exe clave_privada.pem")
        return 1

    url = sys.argv[1].strip()
    version = sys.argv[2].strip()
    ruta_exe = sys.argv[3].strip()
    ruta_clave = sys.argv[4].strip()

    if not os.path.isfile(ruta_exe):
        print(f"Error: No se encontró el ejecutable en {ruta_exe}")
        return 1
        
    if not os.path.isfile(ruta_clave):
        print(f"Error: No se encontró la clave privada en {ruta_clave}")
        return 1

    try:
        # 1. Leer la clave privada
        with open(ruta_clave, "rb") as f:
            sk = ecdsa.SigningKey.from_pem(f.read())

        # 2. Leer el archivo y calcular firma y SHA256
        with open(ruta_exe, "rb") as f:
            file_data = f.read()
            
        sha256 = hashlib.sha256(file_data).hexdigest()
        firma_bytes = sk.sign(file_data, hashfunc=hashlib.sha256)
        firma_base64 = base64.b64encode(firma_bytes).decode('utf-8')
        
        # 3. Subir a Firebase
        from src.database.firebase_client import configurar_url_actualizacion_agente
        configurar_url_actualizacion_agente(url, version=version, sha256=sha256, firma=firma_base64)
        
        print("¡Actualización FIRMADA y configurada en Firebase con éxito!")
        print(f"  URL: {url}")
        print(f"  Versión: {version}")
        print(f"  SHA256: {sha256}")
        print(f"  Firma: {firma_base64[:30]}...")
    except Exception as e:
        print(f"Error durante el proceso: {e}")
        return 1
        
if __name__ == "__main__":
    sys.exit(main())