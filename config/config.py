import os

# 1. Detectar la carpeta donde está este archivo (MiniAgente/config)
CURRENT_DIR = os.path.dirname(os.path.abspath(__file__))

# 2. Subir un nivel para llegar a la raíz (MiniAgente/)
BASE_DIR = os.path.dirname(CURRENT_DIR)

# 3. Apuntar correctamente a la carpeta 'auth'
FIREBASE_JSON_PATH = os.path.join(BASE_DIR, "auth", "serviceAccountKey.json")

# Configuración de Firebase
FIREBASE_COLLECTION_NAME = "computadoras"
VERSION = "1.0.0"
DEBUG_MODE = True