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
VERSION = "5.9.0"
DEBUG_MODE = False

# ---------------------------------------------------------------------------
# AUDITORÍA DE HARDWARE — detectar cambios no autorizados en componentes
# ---------------------------------------------------------------------------
HARDWARE_AUDIT_ENABLED = True
HARDWARE_AUDIT_TTL_DIAS = 90
HARDWARE_AUDIT_LIMPIEZA_BATCH = 100
HARDWARE_AUDIT_LIMPIEZA_INTERVALO_SEG = 86400  # 1 vez por día, junto a limpiar_logs_debug

# ---------------------------------------------------------------------------
# SEGURIDAD — Módulo de actualización remota
# ---------------------------------------------------------------------------

# Dominios HTTPS desde los cuales se permite descargar actualizaciones del agente.
# Solo se aceptará una URL cuyo host sea exactamente uno de estos dominios
# o un subdominio de ellos. Cualquier otra URL será rechazada antes de la descarga.
# Para GitHub Releases los binarios se sirven desde objects.githubusercontent.com.
UPDATE_ALLOWED_DOMAINS: list[str] = [
    "objects.githubusercontent.com",
    "github.com",
    "releases.githubusercontent.com",
    "api.github.com",
]

# Antigüedad máxima (en segundos) que se acepta para un comando ACTUALIZAR_AGENTE.
# Comandos más viejos que este valor son descartados para prevenir ataques de replay.
# Por defecto: 10 minutos.
UPDATE_COMMAND_MAX_AGE_SECONDS: int = 600
