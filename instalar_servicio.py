"""
Script de instalación del Agente de Monitoreo como Servicio de Windows

IMPORTANTE: Ejecutar como Administrador

Uso:
    Instalador.bat install   - Instala el servicio
    Instalador.bat start     - Inicia el servicio
    Instalador.bat stop      - Detiene el servicio
    Instalador.bat remove    - Desinstala el servicio
"""

import sys
import os

def main():
    print("\n" + "="*60)
    print("   INSTALADOR - Agente de Monitoreo como Servicio")
    print("="*60 + "\n")
    
    # Verificar permisos de administrador
    try:
        import ctypes
        if not ctypes.windll.shell32.IsUserAnAdmin():
            print("❌ ERROR: Este script requiere permisos de Administrador")
            print("\nClick derecho → 'Ejecutar como administrador'\n")
            input("Presiona Enter para salir...")
            return
    except:
        pass
    
    print("Opciones disponibles:")
    print("  1. Instalar servicio")
    print("  2. Iniciar servicio")
    print("  3. Detener servicio")
    print("  4. Desinstalar servicio")
    print("  5. Estado del servicio")
    print("  0. Salir")
    print()
    
    while True:
        opcion = input("Selecciona una opción: ").strip()
        
        if opcion == "1":
            instalar_servicio()
        elif opcion == "2":
            iniciar_servicio()
        elif opcion == "3":
            detener_servicio()
        elif opcion == "4":
            desinstalar_servicio()
        elif opcion == "5":
            estado_servicio()
        elif opcion == "0":
            break
        else:
            print("❌ Opción inválida")
        
        print()

def instalar_servicio():
    """Instala el servicio de Windows"""
    print("\n🔧 Instalando servicio...")
    
    # Obtener ruta del ejecutable compilado
    if getattr(sys, 'frozen', False):
        exe_path = sys.executable
    else:
        exe_path = os.path.join(os.getcwd(), "dist", "AgenteMonitoreo.exe")
    
    if not os.path.exists(exe_path):
        print(f"❌ No se encontró el ejecutable en: {exe_path}")
        print("   Compilá primero con PyInstaller")
        return
    
    import subprocess
    
    # Instalar usando sc (Service Control)
    comando = f'sc create "AgenteMonitoreo" binPath= "{exe_path}" start= auto DisplayName= "Agente de Monitoreo - Inventario PC"'
    
    resultado = subprocess.run(comando, shell=True, capture_output=True, text=True)
    
    if "CORRECTO" in resultado.stdout or "SUCCESS" in resultado.stdout:
        print("✅ Servicio instalado exitosamente")
        print(f"   Ruta: {exe_path}")
        
        # Configurar descripción
        subprocess.run(
            f'sc description "AgenteMonitoreo" "Servicio de monitoreo y sincronización de inventario con Firebase"',
            shell=True, capture_output=True
        )
    else:
        print(f"❌ Error instalando servicio:")
        print(resultado.stdout)
        print(resultado.stderr)

def iniciar_servicio():
    """Inicia el servicio"""
    print("\n▶️  Iniciando servicio...")
    import subprocess
    
    resultado = subprocess.run('sc start "AgenteMonitoreo"', shell=True, capture_output=True, text=True)
    
    if "CORRECTO" in resultado.stdout or "RUNNING" in resultado.stdout or "START_PENDING" in resultado.stdout:
        print("✅ Servicio iniciado correctamente")
    else:
        print(f"❌ Error iniciando servicio:")
        print(resultado.stdout)

def detener_servicio():
    """Detiene el servicio"""
    print("\n⏸️  Deteniendo servicio...")
    import subprocess
    
    resultado = subprocess.run('sc stop "AgenteMonitoreo"', shell=True, capture_output=True, text=True)
    
    if "CORRECTO" in resultado.stdout or "STOPPED" in resultado.stdout or "STOP_PENDING" in resultado.stdout:
        print("✅ Servicio detenido correctamente")
    else:
        print(f"⚠️ {resultado.stdout}")

def desinstalar_servicio():
    """Desinstala el servicio"""
    print("\n🗑️  Desinstalando servicio...")
    import subprocess
    
    # Primero intentar detenerlo
    subprocess.run('sc stop "AgenteMonitoreo"', shell=True, capture_output=True)
    
    import time
    time.sleep(2)
    
    # Luego eliminarlo
    resultado = subprocess.run('sc delete "AgenteMonitoreo"', shell=True, capture_output=True, text=True)
    
    if "CORRECTO" in resultado.stdout or "SUCCESS" in resultado.stdout or "marcado" in resultado.stdout:
        print("✅ Servicio desinstalado correctamente")
    else:
        print(f"❌ Error desinstalando servicio:")
        print(resultado.stdout)

def estado_servicio():
    """Muestra el estado del servicio"""
    print("\n📊 Estado del servicio:")
    import subprocess
    
    resultado = subprocess.run('sc query "AgenteMonitoreo"', shell=True, capture_output=True, text=True)
    print(resultado.stdout)

if __name__ == "__main__":
    main()
    print("\n✅ Proceso finalizado")
    input("Presiona Enter para salir...")