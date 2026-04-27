import ecdsa
import os

def generar_claves():
    print("Generando par de claves ECDSA (NIST256p)...")
    private_key = ecdsa.SigningKey.generate(curve=ecdsa.NIST256p)
    public_key = private_key.get_verifying_key()

    with open("clave_privada.pem", "wb") as f:
        f.write(private_key.to_pem())
    with open("clave_publica.pem", "wb") as f:
        f.write(public_key.to_pem())

    print("¡Claves generadas con éxito!\n")
    print("⚠️ IMPORTANTE:")
    print("1. Guarda 'clave_privada.pem' en un lugar seguro. NO la subas al repositorio.")
    print("2. Copia el siguiente contenido y pégalo en 'src/core/auto_update.py' en la variable PUBLIC_KEY_PEM:\n")
    print(public_key.to_pem().decode("utf-8"))

if __name__ == "__main__":
    generar_claves()