"""
Instalador Automático del Agente de Monitoreo
Instala y arranca el servicio en un solo paso

IMPORTANTE: Ejecutar como Administrador
"""

import subprocess
import sys
import os
import time

def verificar_admin():
    """Verifica si tiene permisos de administrador"""
    try:
        import ctypes
        return ctypes.windll.shell32.IsUserAnAdmin()
    except:
        return False

def instalar_y_arrancar():
    """Instala e inicia el servicio automáticamente"""
    
    print("="*60)
    print("  INSTALADOR AUTOMÁTICO - Agente de Monitoreo")
    print("="*60)
    print()
    
    # Verificar permisos
    if not verificar_admin():
        print("❌ ERROR: Se requieren permisos de Administrador")
        print()
        print("Para instalar:")
        print("1. Click derecho en este archivo")
        print("2. Seleccionar 'Ejecutar como administrador'")
        print()
        input("Presiona Enter para salir...")
        return False
    
    # Obtener ruta del ejecutable
    if getattr(sys, 'frozen', False):
        # Si este script está compilado
        carpeta = os.path.dirname(sys.executable)
    else:
        # Si se ejecuta como .py
        carpeta = os.path.dirname(os.path.abspath(__file__))
    
    exe_path = os.path.join(carpeta, "AgenteMonitoreo.exe")
    
    if not os.path.exists(exe_path):
        print(f"❌ No se encontró AgenteMonitoreo.exe en:")
        print(f"   {carpeta}")
        print()
        input("Presiona Enter para salir...")
        return False
    
    print(f"✅ Ejecutable encontrado: {exe_path}")
    print()
    
    # Paso 1: Verificar si ya existe y detenerlo/eliminarlo
    print("🔍 Verificando servicio existente...")
    resultado = subprocess.run(
        'sc query "AgenteMonitoreo"',
        shell=True,
        capture_output=True,
        text=True
    )
    
    if resultado.returncode == 0:
        print("   Servicio existente encontrado, eliminando...")
        subprocess.run('sc stop "AgenteMonitoreo"', shell=True, capture_output=True)
        time.sleep(2)
        subprocess.run('sc delete "AgenteMonitoreo"', shell=True, capture_output=True)
        time.sleep(2)
    
    # Paso 2: Crear el servicio
    print("🔧 Instalando servicio...")
    
    comando_crear = f'sc create "AgenteMonitoreo" binPath= "{exe_path}" start= auto DisplayName= "Agente de Monitoreo - Inventario PC"'
    
    resultado = subprocess.run(comando_crear, shell=True, capture_output=True, text=True)
    
    if "CORRECTO" in resultado.stdout or "SUCCESS" in resultado.stdout:
        print("✅ Servicio instalado correctamente")
        
        # Configurar descripción
        subprocess.run(
            'sc description "AgenteMonitoreo" "Servicio de monitoreo y sincronización de inventario con Firebase"',
            shell=True,
            capture_output=True
        )
        
        # Paso 3: Iniciar el servicio
        print("▶️  Iniciando servicio...")
        time.sleep(1)
        
        resultado_inicio = subprocess.run(
            'sc start "AgenteMonitoreo"',
            shell=True,
            capture_output=True,
            text=True
        )
        
        if "CORRECTO" in resultado_inicio.stdout or "RUNNING" in resultado_inicio.stdout or "START_PENDING" in resultado_inicio.stdout:
            print("✅ Servicio iniciado correctamente")
            print()
            print("="*60)
            print("  ✅ INSTALACIÓN COMPLETADA EXITOSAMENTE")
            print("="*60)
            print()
            print("El agente ya está corriendo en segundo plano.")
            print("Se iniciará automáticamente cada vez que arranque Windows.")
            print()
            print("Para verificar el estado:")
            print('  sc query "AgenteMonitoreo"')
            print()
            return True
        else:
            print("⚠️ El servicio se instaló pero hubo un problema al iniciarlo:")
            print(resultado_inicio.stdout)
            print()
            print("Intentá iniciarlo manualmente con:")
            print('  sc start "AgenteMonitoreo"')
            return False
    else:
        print("❌ Error al instalar el servicio:")
        print(resultado.stdout)
        print(resultado.stderr)
        return False

if __name__ == "__main__":
    exito = instalar_y_arrancar()
    
    print()
    input("Presiona Enter para salir...")
    
    sys.exit(0 if exito else 1)