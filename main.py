"""
Agente de Monitoreo - Main
Puede ejecutarse como:
1. Aplicación normal (.exe)
2. Servicio de Windows (cuando se instala con instalar_servicio.py)
"""

from src.core.scanner import obtener_datos_pc
from src.database.firebase_client import enviar_datos_pc, escuchar_comandos_remotos
from config.config import VERSION, DEBUG_MODE
import time
import sys
import winreg

# Detectar si estamos corriendo como servicio de Windows
try:
    import win32serviceutil
    import win32service
    import win32event
    import servicemanager
    RUNNING_AS_SERVICE = True
except ImportError:
    RUNNING_AS_SERVICE = False


def verificar_autoinicio():
    """Verifica si ya está registrado en el Registry para autoinicio"""
    try:
        ruta_exe = sys.executable
        key_path = r"Software\Microsoft\Windows\CurrentVersion\Run"
        
        # Intentar leer la clave actual
        try:
            key = winreg.OpenKey(winreg.HKEY_CURRENT_USER, key_path, 0, winreg.KEY_READ)
            valor_actual, _ = winreg.QueryValueEx(key, "AgenteMonitoreo")
            winreg.CloseKey(key)
            
            if valor_actual == ruta_exe:
                if DEBUG_MODE:
                    print("✅ Autoinicio ya configurado")
                return
        except FileNotFoundError:
            pass  # La clave no existe, hay que crearla
        
        # Crear/actualizar la clave
        key = winreg.OpenKey(winreg.HKEY_CURRENT_USER, key_path, 0, winreg.KEY_SET_VALUE)
        winreg.SetValueEx(key, "AgenteMonitoreo", 0, winreg.REG_SZ, ruta_exe)
        winreg.CloseKey(key)
        
        if DEBUG_MODE:
            print(f"✅ Autoinicio configurado: {ruta_exe}")
        
    except Exception as e:
        if DEBUG_MODE:
            print(f"⚠️ Error configurando autoinicio: {e}")


def ejecutar_agente_loop():
    """Lógica principal del agente (común para servicio y exe)"""
    # Obtener datos de la PC
    if DEBUG_MODE:
        print("🔍 Escaneando hardware...")
    
    datos = obtener_datos_pc()
    uuid = datos['uuid']

    # Agregar metadata
    datos["version_agente"] = VERSION

    # Sincronizar inventario
    if DEBUG_MODE:
        print(f"☁️  Sincronizando UUID: {uuid}...")
    
    enviar_datos_pc(datos)

    # Escuchar comandos remotos
    escuchar_comandos_remotos(uuid)

    if DEBUG_MODE:
        print(f"🚀 Agente activo. UUID: {uuid}")
        print("   Presioná Ctrl+C para detener")

    # Bucle infinito para mantener el agente escuchando
    try:
        while True:
            time.sleep(1) 
    except KeyboardInterrupt:
        if DEBUG_MODE:
            print("\n👋 Agente detenido")


# ============= SERVICIO DE WINDOWS =============
if RUNNING_AS_SERVICE:
    class AgenteMonitoreoService(win32serviceutil.ServiceFramework):
        _svc_name_ = "AgenteMonitoreo"
        _svc_display_name_ = "Agente de Monitoreo - Inventario PC"
        _svc_description_ = "Servicio de monitoreo y sincronización de inventario con Firebase"

        def __init__(self, args):
            win32serviceutil.ServiceFramework.__init__(self, args)
            self.stop_event = win32event.CreateEvent(None, 0, 0, None)
            self.running = True

        def SvcStop(self):
            self.ReportServiceStatus(win32service.SERVICE_STOP_PENDING)
            win32event.SetEvent(self.stop_event)
            self.running = False

        def SvcDoRun(self):
            servicemanager.LogMsg(
                servicemanager.EVENTLOG_INFORMATION_TYPE,
                servicemanager.PYS_SERVICE_STARTED,
                (self._svc_name_, '')
            )
            
            try:
                datos = obtener_datos_pc()
                uuid = datos['uuid']
                datos["version_agente"] = VERSION
                
                enviar_datos_pc(datos)
                escuchar_comandos_remotos(uuid)
                
                # Mantener el servicio corriendo
                while self.running:
                    for _ in range(300):  # 5 minutos
                        if not self.running:
                            break
                        time.sleep(1)
                    
                    if self.running:
                        datos = obtener_datos_pc()
                        datos["version_agente"] = VERSION
                        enviar_datos_pc(datos)
                        
            except Exception as e:
                servicemanager.LogErrorMsg(f"Error en servicio: {str(e)}")


# ============= PUNTO DE ENTRADA =============
if __name__ == "__main__":
    # Si se pasan argumentos de servicio (install, start, stop, remove)
    if RUNNING_AS_SERVICE and len(sys.argv) > 1:
        win32serviceutil.HandleCommandLine(AgenteMonitoreoService)
    else:
        # Modo aplicación normal
        if DEBUG_MODE:
            print(f"\n--- 🛠️ MODO DESARROLLO: Ejecutando Agente V.{VERSION} ---")
        
        # Verificar y configurar autoinicio (solo en modo normal, no servicio)
        verificar_autoinicio()
        
        # Ejecutar agente
        ejecutar_agente_loop()