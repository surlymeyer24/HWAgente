"""
Agente de Monitoreo - Auto-instalable
Se instala automáticamente como servicio de Windows si no lo está
"""

from src.core.scanner import obtener_datos_pc
from src.database.firebase_client import enviar_datos_pc, escuchar_comandos_remotos
from config.config import VERSION, DEBUG_MODE
import time
import sys
import subprocess
import os

# Detectar si estamos corriendo como servicio de Windows
try:
    import win32serviceutil
    import win32service
    import win32event
    import servicemanager
    RUNNING_AS_SERVICE = True
except ImportError:
    RUNNING_AS_SERVICE = False


def verificar_permisos_admin():
    """Verifica si tiene permisos de administrador"""
    try:
        import ctypes
        return ctypes.windll.shell32.IsUserAnAdmin()
    except:
        return False


def solicitar_permisos_admin():
    """Solicita permisos de administrador y reinicia el programa"""
    try:
        import ctypes
        if sys.argv[-1] != 'asadmin':
            script = sys.executable
            params = ' '.join([script] + sys.argv + ['asadmin'])
            ctypes.windll.shell32.ShellExecuteW(None, "runas", sys.executable, params, None, 1)
            return True
    except:
        pass
    return False


def servicio_esta_instalado():
    """Verifica si el servicio ya está instalado"""
    try:
        resultado = subprocess.run(
            'sc query "AgenteMonitoreo"',
            shell=True,
            capture_output=True,
            text=True,
            creationflags=subprocess.CREATE_NO_WINDOW
        )
        return resultado.returncode == 0
    except:
        return False


def instalar_servicio_automaticamente():
    """Instala el servicio automáticamente"""
    print("\n" + "="*60)
    print("  INSTALACIÓN AUTOMÁTICA DEL SERVICIO")
    print("="*60 + "\n")
    
    exe_path = sys.executable
    
    print(f"📍 Ruta del ejecutable: {exe_path}")
    print("🔧 Instalando servicio...\n")
    
    # Detener y eliminar si existe
    subprocess.run('sc stop "AgenteMonitoreo"', shell=True, capture_output=True, creationflags=subprocess.CREATE_NO_WINDOW)
    time.sleep(1)
    subprocess.run('sc delete "AgenteMonitoreo"', shell=True, capture_output=True, creationflags=subprocess.CREATE_NO_WINDOW)
    time.sleep(1)
    
    # Crear servicio
    comando = f'sc create "AgenteMonitoreo" binPath= "{exe_path}" start= auto DisplayName= "Agente de Monitoreo - Inventario PC"'
    resultado = subprocess.run(comando, shell=True, capture_output=True, text=True, creationflags=subprocess.CREATE_NO_WINDOW)
    
    if "CORRECTO" in resultado.stdout or "SUCCESS" in resultado.stdout:
        print("✅ Servicio instalado correctamente")
        
        # Agregar descripción
        subprocess.run(
            'sc description "AgenteMonitoreo" "Servicio de monitoreo y sincronización de inventario con Firebase"',
            shell=True,
            capture_output=True,
            creationflags=subprocess.CREATE_NO_WINDOW
        )
        
        # Iniciar servicio
        print("▶️  Iniciando servicio...")
        time.sleep(1)
        
        resultado_inicio = subprocess.run(
            'sc start "AgenteMonitoreo"',
            shell=True,
            capture_output=True,
            text=True,
            creationflags=subprocess.CREATE_NO_WINDOW
        )
        
        if "CORRECTO" in resultado_inicio.stdout or "RUNNING" in resultado_inicio.stdout:
            print("✅ Servicio iniciado correctamente\n")
            print("="*60)
            print("  ✅ INSTALACIÓN COMPLETADA")
            print("="*60)
            print("\nEl agente está corriendo en segundo plano.")
            print("Se iniciará automáticamente con Windows.\n")
            return True
        else:
            print("⚠️ Instalado pero no se pudo iniciar automáticamente")
            print("Inicialo manualmente con: sc start AgenteMonitoreo\n")
            return False
    else:
        print("❌ Error al instalar el servicio:")
        print(resultado.stdout)
        return False


def ejecutar_agente_loop():
    """Lógica principal del agente"""
    datos = obtener_datos_pc()
    uuid = datos['uuid']
    datos["version_agente"] = VERSION
    
    enviar_datos_pc(datos)
    escuchar_comandos_remotos(uuid)
    
    # Mantener corriendo
    while True:
        time.sleep(1)


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
    # Si se pasan comandos de servicio específicos (install, start, stop, remove, etc)
    service_commands = ['install', 'update', 'remove', 'start', 'stop', 'restart', 'debug']
    if RUNNING_AS_SERVICE and len(sys.argv) > 1 and sys.argv[1].lower() in service_commands:
        win32serviceutil.HandleCommandLine(AgenteMonitoreoService)
    else:
        # Modo aplicación normal - Auto-instalación
        
        # Verificar si ya está instalado como servicio
        if servicio_esta_instalado():
            # Ya está instalado, verificar que esté corriendo
            resultado = subprocess.run(
                'sc query "AgenteMonitoreo"',
                shell=True,
                capture_output=True,
                text=True,
                creationflags=subprocess.CREATE_NO_WINDOW
            )
            
            if "RUNNING" in resultado.stdout:
                print("✅ El servicio ya está instalado y corriendo")
                print("\nNo es necesario ejecutar el agente manualmente.")
                print("Para administrar el servicio, usá:")
                print('  sc stop "AgenteMonitoreo"  - Detener')
                print('  sc start "AgenteMonitoreo" - Iniciar')
                print('  sc delete "AgenteMonitoreo" - Desinstalar')
            else:
                print("⚠️ El servicio está instalado pero no está corriendo")
                print("Iniciando servicio...")
                subprocess.run('sc start "AgenteMonitoreo"', shell=True, creationflags=subprocess.CREATE_NO_WINDOW)
            
            if DEBUG_MODE:
                print()
                input("Presiona Enter para salir...")
            sys.exit(0)
        
        # No está instalado - Instalar automáticamente
        print(f"\n--- Agente de Monitoreo V.{VERSION} ---")
        print("\n🔍 Detectando configuración...")
        print("   El servicio no está instalado\n")
        
        # Verificar permisos de administrador
        if not verificar_permisos_admin():
            print("⚠️  Se requieren permisos de Administrador para instalar el servicio")
            print("\nSolicitando permisos...")
            
            if solicitar_permisos_admin():
                # Se solicitó elevación, el proceso se reiniciará
                sys.exit(0)
            else:
                print("\n❌ No se pudieron obtener permisos de administrador")
                print("\nPara instalar manualmente:")
                print("1. Click derecho en este ejecutable")
                print("2. Seleccionar 'Ejecutar como administrador'")
                if DEBUG_MODE:
                    print()
                    input("Presiona Enter para salir...")
                sys.exit(1)
        
        # Tiene permisos, instalar
        if instalar_servicio_automaticamente():
            if DEBUG_MODE:
                print()
                input("Presiona Enter para salir...")
            sys.exit(0)
        else:
            if DEBUG_MODE:
                print()
                input("Presiona Enter para salir...")
            sys.exit(1)