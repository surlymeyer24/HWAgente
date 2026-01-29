import os
import sys

# Detectar si está corriendo como .exe compilado o como script
if getattr(sys, 'frozen', False):
    # Si está compilado con PyInstaller
    # PyInstaller extrae archivos en sys._MEIPASS (carpeta temporal)
    BASE_DIR = sys._MEIPASS
else:
    # Si se ejecuta como script Python
    CURRENT_DIR = os.path.dirname(os.path.abspath(__file__))
    BASE_DIR = os.path.dirname(CURRENT_DIR)

# Apuntar correctamente a la carpeta 'auth'
FIREBASE_JSON_PATH = os.path.join(BASE_DIR, "auth", "serviceAccountKey.json")

# Configuración de Firebase
FIREBASE_COLLECTION_NAME = "computadoras"
VERSION = "1.0.0"
DEBUG_MODE = True