import os
import sys

def get_base_path():
    # PyInstaller extrae archivos en sys._MEIPASS
    if getattr(sys, 'frozen', False):
        return sys._MEIPASS
    # En desarrollo, sube dos niveles desde config/config.py
    return os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

BASE_DIR = get_base_path()

# Rutas absolutas garantizadas
FIREBASE_JSON_PATH = os.path.join(BASE_DIR, "auth", "serviceAccountKey.json")
FIREBASE_COLLECTION_NAME = "computadoras"
VERSION = "1.0.0"
DEBUG_MODE = True