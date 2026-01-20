from src.core.scanner import obtener_datos_pc
from src.database.firebase_client import enviar_datos_pc
from config.config import VERSION, DEBUG_MODE
import time

def ejecutar_agente():
    # Mensaje de encabezado con versión
    if DEBUG_MODE:
        print(f"\n--- 🛠️ MODO DESARROLLO: Ejecutando Agente V.{VERSION} ---")
    else:
        print(f"\n--- Agente de Inventario V.{VERSION} ---")
    
    try:
        # Escaneo
        print("🔍 Escaneando hardware y usuarios...")
        datos_hardware = obtener_datos_pc()
        
        # Metadata (Agregamos la versión también a los datos que suben)
        datos_hardware["version_agente"] = VERSION
        datos_hardware["ultima_actualizacion"] = time.strftime("%Y-%m-%d %H:%M:%S")
        
        # Sincronización
        print(f"☁️  Sincronizando UUID: {datos_hardware['uuid']}...")
        enviar_datos_pc(datos_hardware)
        
        print("✅ Sincronización finalizada.")
        
    except Exception as e:
        print(f"❌ Error en la ejecución: {e}")

if __name__ == "__main__":
    ejecutar_agente()