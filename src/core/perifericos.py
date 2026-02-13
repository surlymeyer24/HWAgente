import subprocess
import re
import json

# ==================== MONITORES ====================
def obtener_monitores():
    """Obtiene información de monitores conectados"""
    monitores = []
    
    try:
        # PowerShell para obtener info de monitores con WMI
        ps_script = """
        Get-WmiObject -Namespace root\\wmi -Class WmiMonitorBasicDisplayParams | 
        ForEach-Object {
            $monitor = $_
            $id = $monitor.InstanceName
            
            # Obtener nombre del monitor
            $name = (Get-WmiObject -Namespace root\\wmi -Class WmiMonitorID | 
                    Where-Object {$_.InstanceName -eq $id}).UserFriendlyName
            
            if ($name) {
                $nameStr = -join ($name | ForEach-Object {[char]$_})
            } else {
                $nameStr = "Monitor Genérico"
            }
            
            [PSCustomObject]@{
                Nombre = $nameStr
                AnchoMM = $monitor.MaxHorizontalImageSize
                AltoMM = $monitor.MaxVerticalImageSize
                AnchoCM = [math]::Round($monitor.MaxHorizontalImageSize / 10, 1)
                AltoCM = [math]::Round($monitor.MaxVerticalImageSize / 10, 1)
            }
        } | ConvertTo-Json
        """
        
        resultado = subprocess.run(
            ['powershell', '-NoProfile', '-Command', ps_script],
            capture_output=True,
            text=True,
            timeout=10,
            creationflags=subprocess.CREATE_NO_WINDOW
        )
        
        if resultado.returncode == 0 and resultado.stdout.strip():
            datos = json.loads(resultado.stdout)
            
            # Si es un solo monitor, convertir a lista
            if isinstance(datos, dict):
                datos = [datos]
            
            for monitor in datos:
                monitores.append({
                    'nombre': monitor.get('Nombre', 'Desconocido').strip(),
                    'ancho_cm': monitor.get('AnchoCM', 0),
                    'alto_cm': monitor.get('AltoCM', 0),
                    'pulgadas': calcular_pulgadas(
                        monitor.get('AnchoCM', 0), 
                        monitor.get('AltoCM', 0)
                    )
                })
        
        # Obtener resoluciones actuales
        resoluciones = obtener_resoluciones_monitores()
        
        # Combinar información
        for i, monitor in enumerate(monitores):
            if i < len(resoluciones):
                monitor['resolucion'] = resoluciones[i]
            else:
                monitor['resolucion'] = 'Desconocida'
                
    except Exception as e:
        print(f"⚠️ Error obteniendo monitores: {e}")
        monitores.append({
            'nombre': 'Error al detectar',
            'error': str(e)
        })
    
    # Si no se detectó ningún monitor, agregar uno genérico
    if not monitores:
        monitores.append({
            'nombre': 'Monitor detectado',
            'resolucion': obtener_resoluciones_monitores()[0] if obtener_resoluciones_monitores() else 'Desconocida'
        })
    
    return monitores


def calcular_pulgadas(ancho_cm, alto_cm):
    """Calcula pulgadas diagonales del monitor"""
    try:
        if ancho_cm > 0 and alto_cm > 0:
            diagonal_cm = (ancho_cm**2 + alto_cm**2)**0.5
            pulgadas = diagonal_cm / 2.54
            return round(pulgadas, 1)
    except:
        pass
    return 0


def obtener_resoluciones_monitores():
    """Obtiene las resoluciones actuales de los monitores"""
    resoluciones = []
    
    try:
        ps_script = """
        Add-Type -AssemblyName System.Windows.Forms
        [System.Windows.Forms.Screen]::AllScreens | 
        ForEach-Object {
            [PSCustomObject]@{
                Ancho = $_.Bounds.Width
                Alto = $_.Bounds.Height
                Principal = $_.Primary
            }
        } | ConvertTo-Json
        """
        
        resultado = subprocess.run(
            ['powershell', '-NoProfile', '-Command', ps_script],
            capture_output=True,
            text=True,
            timeout=5,
            creationflags=subprocess.CREATE_NO_WINDOW
        )
        
        if resultado.returncode == 0 and resultado.stdout.strip():
            datos = json.loads(resultado.stdout)
            
            if isinstance(datos, dict):
                datos = [datos]
            
            for pantalla in datos:
                res = f"{pantalla['Ancho']}x{pantalla['Alto']}"
                if pantalla.get('Principal'):
                    res += " (Principal)"
                resoluciones.append(res)
                
    except Exception as e:
        print(f"⚠️ Error obteniendo resoluciones: {e}")
    
    return resoluciones


# ==================== IMPRESORAS ====================
def obtener_impresoras():
    """Obtiene impresoras instaladas (locales y de red)"""
    impresoras = []
    
    try:
        ps_script = """
        Get-Printer | Select-Object Name, DriverName, PortName, 
                     @{Name='Tipo';Expression={
                         if ($_.Type -eq 'Local') {'Local'} 
                         elseif ($_.Type -eq 'Connection') {'Red'} 
                         else {$_.Type}
                     }},
                     @{Name='Estado';Expression={
                         if ($_.PrinterStatus -eq 3) {'Inactiva'} 
                         elseif ($_.PrinterStatus -eq 4) {'Imprimiendo'} 
                         else {'Disponible'}
                     }},
                     Shared,
                     @{Name='Predeterminada';Expression={
                         $defaultPrinter = (Get-WmiObject Win32_Printer | Where-Object {$_.Default -eq $true}).Name
                         $_.Name -eq $defaultPrinter
                     }} | 
        ConvertTo-Json
        """
        
        resultado = subprocess.run(
            ['powershell', '-NoProfile', '-Command', ps_script],
            capture_output=True,
            text=True,
            timeout=10,
            creationflags=subprocess.CREATE_NO_WINDOW
        )
        
        if resultado.returncode == 0 and resultado.stdout.strip():
            datos = json.loads(resultado.stdout)
            
            if isinstance(datos, dict):
                datos = [datos]
            
            for impresora in datos:
                impresoras.append({
                    'nombre': impresora.get('Name', 'Desconocida'),
                    'driver': impresora.get('DriverName', 'N/A'),
                    'puerto': impresora.get('PortName', 'N/A'),
                    'tipo': impresora.get('Tipo', 'Desconocido'),
                    'estado': impresora.get('Estado', 'Desconocido'),
                    'compartida': impresora.get('Shared', False),
                    'predeterminada': impresora.get('Predeterminada', False)
                })
                
    except Exception as e:
        print(f"⚠️ Error obteniendo impresoras: {e}")
    
    return impresoras


# ==================== DISPOSITIVOS USB ====================
# Términos a excluir: infraestructura USB interna, no periféricos reales
# Incluye equivalentes en inglés y español (Windows localizado)
_EXCLUIR_USB = [
    'root hub', 'host controller', 'generic usb hub', 'usb root hub',
    'usb composite device', 'composite usb device',
    'usb hub', 'enhanced host controller', 'extensible host controller',
    'xhc host controller', 'usb serial converter',
    # Español (y variantes por codificación)
    'concentrador raíz', 'concentrador raiz', 'concentrador ra', 'concentrador usb',
    'dispositivo compuesto usb', 'controladora de host', 'controlador de host',
    'concentradores usb', 'controladora de host',
]
# HID genéricos que representan teclado/mouse (se consolidan en uno)
_HID_GENERICOS = ('dispositivo de entrada usb', 'usb input device', 'hid-compliant')

# Mapeo de clases a categorías amigables
_CATEGORIAS_USB = {
    'HIDClass': 'Teclado/Mouse/Controlador',
    'Image': 'Cámara/Scanner',
    'Media': 'Audio/Video',
    'DiskDrive': 'Almacenamiento (pendrive/disco)',
    'Printer': 'Impresora',
    'Bluetooth': 'Bluetooth',
    'Biometric': 'Huella/Biometría',
    'SmartCardReader': 'Lector de tarjetas',
    'Net': 'Adaptador de red USB',
}


def _normalizar_para_comparacion(texto: str) -> str:
    """Normaliza texto para comparación (evita problemas de codificación í/ı)"""
    if not texto:
        return ''
    t = texto.lower().strip()
    # Normalizar acentos comunes que pueden llegar mal codificados
    for old, new in [('í', 'i'), ('á', 'a'), ('é', 'e'), ('ó', 'o'), ('ú', 'u'), ('ñ', 'n')]:
        t = t.replace(old, new)
    return t


def _es_dispositivo_excluido(nombre: str) -> bool:
    """Verifica si el dispositivo debe excluirse (infraestructura interna)"""
    nombre_norm = _normalizar_para_comparacion(nombre)
    exclusiones_norm = [_normalizar_para_comparacion(term) for term in _EXCLUIR_USB]
    return any(term in nombre_norm for term in exclusiones_norm)


def _es_hid_generico(nombre: str) -> bool:
    """Verifica si es un HID genérico (teclado/mouse sin nombre de modelo)"""
    nombre_norm = _normalizar_para_comparacion(nombre)
    return any(term in nombre_norm for term in _HID_GENERICOS)


def _normalizar_nombre_usb(nombre: str, fabricante: str) -> str:
    """Evita mostrar 'Desconocido' y mejora nombres genéricos"""
    nombre = (nombre or '').strip()
    fabricante = (fabricante or '').strip()
    if not nombre or nombre.lower() == 'desconocido':
        return fabricante or 'Dispositivo USB'
    # Si el nombre es muy genérico pero tenemos fabricante, combinar
    if fabricante and nombre.lower().startswith(('usb ', 'generic ', 'hid ')):
        return f"{fabricante} - {nombre}"
    return nombre


def obtener_dispositivos_usb():
    """Obtiene periféricos USB conectados (excluye hubs, controladores internos)"""
    dispositivos = []
    vistos = set()  # Evitar duplicados por nombre similar
    
    try:
        ps_script = """
        Get-PnpDevice -PresentOnly | 
        Where-Object {$_.InstanceId -like "*USB*" -and $_.Status -eq "OK"} | 
        Select-Object FriendlyName, Class, Manufacturer | 
        ConvertTo-Json
        """
        
        resultado = subprocess.run(
            ['powershell', '-NoProfile', '-Command', ps_script],
            capture_output=True,
            text=True,
            timeout=10,
            creationflags=subprocess.CREATE_NO_WINDOW
        )
        
        if resultado.returncode == 0 and resultado.stdout.strip():
            datos = json.loads(resultado.stdout)
            
            if isinstance(datos, dict):
                datos = [datos]
            
            for dispositivo in datos:
                nombre = dispositivo.get('FriendlyName', '')
                fabricante = dispositivo.get('Manufacturer', '')
                clase = dispositivo.get('Class', 'Otro')
                
                # Excluir infraestructura interna
                if _es_dispositivo_excluido(nombre):
                    continue
                
                nombre_final = _normalizar_nombre_usb(nombre, fabricante)
                clave = f"{nombre_final}|{clase}"
                
                if clave in vistos:
                    continue
                vistos.add(clave)
                
                categoria = _CATEGORIAS_USB.get(clase, clase)
                
                dispositivos.append({
                    'nombre': nombre_final,
                    'categoria': categoria,
                    'fabricante': fabricante or '—',
                    'clase': clase,
                    '_es_generico_hid': clase == 'HIDClass' and _es_hid_generico(nombre)
                })
            
            # Consolidar teclados/mouse genéricos en una sola línea
            genericos = [d for d in dispositivos if d.pop('_es_generico_hid', False)]
            otros = [d for d in dispositivos if d not in genericos]
            if genericos:
                count = len(genericos)
                otros.append({
                    'nombre': f"Teclado y Mouse" + (f" ({count} dispositivos)" if count > 1 else ""),
                    'categoria': 'Teclado/Mouse/Controlador',
                    'fabricante': '—',
                    'clase': 'HIDClass'
                })
            dispositivos = otros
            
            # Ordenar: primero por categoría, luego por nombre
            dispositivos.sort(key=lambda d: (d['categoria'], d['nombre']))
                
    except Exception as e:
        print(f"⚠️ Error obteniendo dispositivos USB: {e}")
    
    return dispositivos


def formatear_dispositivos_usb(dispositivos: list, usar_emoji: bool = False) -> str:
    """
    Formatea la lista de dispositivos USB para una salida legible.
    
    Args:
        dispositivos: Lista devuelta por obtener_dispositivos_usb()
        usar_emoji: Si True, añade emojis según categoría (puede fallar en consola Windows)
    
    Returns:
        Cadena formateada para mostrar al usuario
    """
    if not dispositivos:
        return "  No se detectaron periféricos USB"
    
    # Iconos ASCII seguros para consola Windows; emojis opcionales
    iconos = {
        'Teclado/Mouse/Controlador': '[KB]' if not usar_emoji else '⌨️',
        'Cámara/Scanner': '[CAM]' if not usar_emoji else '📷',
        'Almacenamiento (pendrive/disco)': '[USB]' if not usar_emoji else '💾',
        'Impresora': '[PRN]' if not usar_emoji else '🖨️',
        'Audio/Video': '[AUD]' if not usar_emoji else '🔊',
        'Bluetooth': '[BT]' if not usar_emoji else '📶',
        'Huella/Biometría': '[BIO]' if not usar_emoji else '👆',
    }
    
    lineas = []
    cat_actual = None
    
    for d in dispositivos:
        cat = d.get('categoria', 'Otro')
        if cat != cat_actual:
            cat_actual = cat
            icono = iconos.get(cat, '[+]' if not usar_emoji else '🔌')
            lineas.append(f"\n  {icono} {cat}:")
        
        nombre = d.get('nombre', 'Desconocido')
        fab = d.get('fabricante', '')
        if fab and fab != '—' and fab not in nombre:
            lineas.append(f"      • {nombre} ({fab})")
        else:
            lineas.append(f"      • {nombre}")
    
    return '\n'.join(lineas).strip() if lineas else "  No se detectaron periféricos USB"


# ==================== DISPOSITIVOS DE AUDIO ====================
def obtener_dispositivos_audio():
    """Obtiene dispositivos de audio (micrófonos, altavoces, etc.)"""
    dispositivos_audio = {
        'entrada': [],  # Micrófonos
        'salida': []    # Altavoces/Auriculares
    }
    
    try:
        # Dispositivos de grabación (entrada)
        ps_entrada = """
        Get-WmiObject Win32_SoundDevice | 
        Where-Object {$_.Status -eq "OK"} |
        Select-Object Name, Manufacturer, Status | 
        ConvertTo-Json
        """
        
        resultado = subprocess.run(
            ['powershell', '-NoProfile', '-Command', ps_entrada],
            capture_output=True,
            text=True,
            timeout=8,
            creationflags=subprocess.CREATE_NO_WINDOW
        )
        
        if resultado.returncode == 0 and resultado.stdout.strip():
            datos = json.loads(resultado.stdout)
            
            if isinstance(datos, dict):
                datos = [datos]
            
            for dispositivo in datos:
                info = {
                    'nombre': dispositivo.get('Name', 'Desconocido'),
                    'fabricante': dispositivo.get('Manufacturer', 'Desconocido'),
                    'estado': 'Activo' if dispositivo.get('Status') == 'OK' else 'Inactivo'
                }
                
                # Clasificar en entrada o salida basado en el nombre
                nombre_lower = info['nombre'].lower()
                if any(palabra in nombre_lower for palabra in ['microphone', 'mic', 'input', 'recording']):
                    dispositivos_audio['entrada'].append(info)
                else:
                    dispositivos_audio['salida'].append(info)
                    
    except Exception as e:
        print(f"⚠️ Error obteniendo dispositivos de audio: {e}")
    
    return dispositivos_audio


# ==================== FUNCIÓN PRINCIPAL ====================
def obtener_todos_los_perifericos():
    """Obtiene todos los periféricos conectados"""
    return {
        'monitores': obtener_monitores(),
        'impresoras': obtener_impresoras(),
        'dispositivos_usb': obtener_dispositivos_usb(),
        'audio': obtener_dispositivos_audio()
    }


# ==================== TESTING ====================
if __name__ == "__main__":
    import pprint
    
    print("=" * 60)
    print("DETECCIÓN DE PERIFÉRICOS")
    print("=" * 60)
    
    perifericos = obtener_todos_los_perifericos()
    
    print("\n[MONITORES]")
    pprint.pprint(perifericos['monitores'])
    
    print("\n[IMPRESORAS]")
    pprint.pprint(perifericos['impresoras'])
    
    print("\n[USB] Dispositivos USB:")
    print(formatear_dispositivos_usb(perifericos['dispositivos_usb']))
    print("\n   (datos crudos):")
    pprint.pprint(perifericos['dispositivos_usb'])
    
    print("\n[AUDIO] Dispositivos de audio:")
    pprint.pprint(perifericos['audio'])