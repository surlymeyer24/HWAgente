from src.core.scanner import obtener_datos_pc
from src.database.firebase_client import enviar_datos_pc, escuchar_comandos_remotos
from config.config import VERSION, DEBUG_MODE
import time
import winreg
import sys

def iniciar_agente():
    datos = obtener_datos_pc()
    uuid = datos['uuid']
    
    # 1. Reporta sus datos actuales (Inventario)
    enviar_datos_pc(datos)
    
    # 2. Crea o verifica su documento de tareas
    # Esto asegura que el documento EXISTA para que vos solo tengas que editarlo
    db.collection("tareas").document(uuid).set({
        "ultimo_comando": "NINGUNO",
        "fecha_conexion": firestore.SERVER_TIMESTAMP
    }, merge=True)
    
    # 3. Se queda escuchando
    escuchar_tareas_remotas(uuid)
def establecer_autoinicio():
    # Obtiene la ruta de donde se está ejecutando el EXE
    ruta_exe = sys.executable 
    key_path = r"Software\Microsoft\Windows\CurrentVersion\Run"
    try:
        key = winreg.OpenKey(winreg.HKEY_CURRENT_USER, key_path, 0, winreg.KEY_SET_VALUE)
        winreg.SetValueEx(key, "AgenteMonitoreo", 0, winreg.REG_SZ, ruta_exe)
        winreg.CloseKey(key)
    except Exception as e:
        print(f"No se pudo configurar el autoinicio: {e}")

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
    datos = obtener_datos_pc()
    uuid = datos['uuid'] # Usamos el UUID real capturado

    # 1. Sincroniza el inventario
    enviar_datos_pc(datos)

    # 2. Crea la colección 'tareas' y se queda escuchando
    escuchar_comandos_remotos(uuid)

    print(f"🚀 Agente activo. UUID: {uuid}")

    # 3. BUCLE INFINITO: Sin esto, el script se cierra y no crea nada
    try:
        while True:
            time.sleep(1) 
    except KeyboardInterrupt:
        print("Detenido")