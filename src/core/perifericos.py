import subprocess
import re
import json

# ==================== MONITORES ====================
_NOMBRES_MONITOR_GENERICOS = {
    'hdmi', 'led', 'lcd', 'monitor', 'monitor generico', 'generic monitor',
    'hdmi1', 'hdmi2', 'hdmi 1', 'hdmi 2', 'vga', 'dvi', 'displayport',
    'color lcd', 'unknown', 'desconocido', 'monitor detectado',
}


def _limpiar_nombre_monitor(nombre: str, pulgadas: float, resolucion: str) -> str:
    """Reemplaza nombres de monitor sin valor (HDMI, LED, etc.) por una descripción útil."""
    nombre_norm = nombre.lower().strip()
    if nombre_norm not in _NOMBRES_MONITOR_GENERICOS:
        return nombre
    if pulgadas and resolucion:
        return f'Monitor {pulgadas}" ({resolucion})'
    if pulgadas:
        return f'Monitor {pulgadas}"'
    if resolucion:
        return f'Monitor ({resolucion})'
    return 'Monitor externo'


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
            encoding='utf-8', errors='replace',
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
        
        # Combinar información y limpiar nombres genéricos
        for i, monitor in enumerate(monitores):
            if i < len(resoluciones):
                monitor['resolucion'] = resoluciones[i]
            else:
                monitor['resolucion'] = 'Desconocida'
            monitor['nombre'] = _limpiar_nombre_monitor(
                monitor['nombre'], monitor.get('pulgadas', 0), monitor.get('resolucion', '')
            )
                
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
            encoding='utf-8', errors='replace',
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
_VIRTUAL_DRIVERS = {
    'pdf', 'xps', 'fax', 'onenote', 'virtual', 'cutepdf', 'novapdf',
    'foxit', 'bullzip', 'dopdf', 'print to', 'microsoft xps',
}
_VIRTUAL_PORTS = {'PORTPROMPT:', 'FILE:', 'NUL:', 'NULPORT:', 'FAX:'}
_VIRTUAL_NAMES = {'pdf', 'xps', 'fax', 'onenote', 'snagit', 'print to', 'virtual printer'}


def _clasificar_impresora(nombre: str, driver: str, puerto: str) -> tuple[str, str | None]:
    """
    Retorna (tipo_impresora, conexion_impresora).
    tipo_impresora: 'fisica' | 'virtual'
    conexion_impresora: 'usb' | 'red' | 'bluetooth' | 'local' | 'desconocida' | None (virtual)
    """
    nombre_l = (nombre or '').lower()
    driver_l = (driver or '').lower()
    puerto_u = (puerto or '').upper().strip()

    es_virtual = (
        any(kw in driver_l for kw in _VIRTUAL_DRIVERS)
        or puerto_u in _VIRTUAL_PORTS
        or any(kw in nombre_l for kw in _VIRTUAL_NAMES)
    )
    if es_virtual:
        return 'virtual', None

    if puerto_u.startswith('USB'):
        conexion = 'usb'
    elif puerto_u.startswith(('IP_', 'WSD-', 'TCP')):
        conexion = 'red'
    elif puerto_u.startswith('BT') or 'BLUETOOTH' in puerto_u:
        conexion = 'bluetooth'
    elif puerto_u.startswith(('LPT', 'COM')):
        conexion = 'local'
    else:
        conexion = 'desconocida'

    return 'fisica', conexion


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
            encoding='utf-8', errors='replace',
            timeout=10,
            creationflags=subprocess.CREATE_NO_WINDOW
        )
        
        if resultado.returncode == 0 and resultado.stdout.strip():
            datos = json.loads(resultado.stdout)
            
            if isinstance(datos, dict):
                datos = [datos]
            
            for impresora in datos:
                nombre = impresora.get('Name', 'Desconocida')
                driver = impresora.get('DriverName', 'N/A')
                puerto = impresora.get('PortName', 'N/A')
                tipo_imp, conexion_imp = _clasificar_impresora(nombre, driver, puerto)
                entry = {
                    'nombre': nombre,
                    'driver': driver,
                    'puerto': puerto,
                    'tipo': impresora.get('Tipo', 'Desconocido'),
                    'estado': impresora.get('Estado', 'Desconocido'),
                    'compartida': impresora.get('Shared', False),
                    'predeterminada': impresora.get('Predeterminada', False),
                    'tipo_impresora': tipo_imp,
                }
                if conexion_imp is not None:
                    entry['conexion_impresora'] = conexion_imp
                impresoras.append(entry)
                
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
    'Keyboard': 'Teclado',
    'Mouse': 'Mouse',
    'HIDClass': 'Controlador HID',
    'Image': 'Cámara/Scanner',
    'Media': 'Audio/Video',
    'DiskDrive': 'Almacenamiento (pendrive/disco)',
    'Printer': 'Impresora',
    'Bluetooth': 'Bluetooth',
    'Biometric': 'Huella/Biometría',
    'SmartCardReader': 'Lector de tarjetas',
    'Net': 'Adaptador de red USB',
}

# Diccionario de Vendor IDs USB → nombre del fabricante
# Fuente: USB-IF (USB Implementers Forum) — marcas más comunes en entornos corporativos
_USB_VENDORS = {
    # Periféricos (teclados, mouse, headsets)
    '046D': 'Logitech',
    '1532': 'Razer',
    '1B1C': 'Corsair',
    '1038': 'SteelSeries',
    '0951': 'Kingston/HyperX',
    '046E': 'Behavior Tech (BTC)',
    '04F2': 'Chicony',
    '0461': 'Primax/Genius',
    '1BCF': 'Rapoo',
    '258A': 'SINO WEALTH (Redragon/genéricos)',
    '3938': 'MOSART (YR/genéricos)',
    '09DA': 'A4Tech',
    '1EA7': 'SHARKOON',
    '28DA': 'Glorious',
    '3434': 'Keychron',
    '320F': 'Ducky',
    '05AC': 'Apple',
    '04D9': 'Holtek (teclados genéricos)',
    '413C': 'Dell',
    '03F0': 'HP',
    '17EF': 'Lenovo',
    '045E': 'Microsoft',
    '04B3': 'IBM',
    '1D57': 'Xenta',
    '248A': 'Maxxter',
    '275D': 'ROCCAT',
    '0C45': 'Microdia (webcams/periféricos)',
    '1A2C': 'China Resource (teclados mecánicos)',
    '04CA': 'Lite-On Technology',
    '0101': 'Logitech (legacy)',
    # Almacenamiento USB
    '0781': 'SanDisk',
    '090C': 'Silicon Motion (pendrives)',
    '058F': 'Alcor Micro (lectores SD)',
    '0BDA': 'Realtek',
    '1005': 'Apacer',
    '13FE': 'Kingston (Phison)',
    '0930': 'Toshiba',
    '1F75': 'Innostor (pendrives)',
    '054C': 'Sony',
    '04E8': 'Samsung',
    '0CF2': 'ENE Technology',
    '8564': 'Transcend',
    '1B1C': 'Corsair',
    '0BC2': 'Seagate',
    '1058': 'Western Digital',
    '152D': 'JMicron (discos externos)',
    '174C': 'ASMedia (discos externos)',
    '2109': 'VIA Labs (hubs/docks)',
    # Impresoras
    '04A9': 'Canon',
    '04B8': 'Epson',
    '03F0': 'HP',
    '04F9': 'Brother',
    '0924': 'Xerox',
    '04E8': 'Samsung',
    '0482': 'Kyocera',
    '06BC': 'OKI',
    '0409': 'NEC',
    # Audio
    '1235': 'Focusrite',
    '0D8C': 'C-Media (audio USB genérico)',
    '08BB': 'Texas Instruments (audio)',
    '1395': 'Sennheiser',
    '0ECB': 'JBL',
    '262A': 'Jabra',
    '2B24': 'HyperX (audio)',
    '0763': 'M-Audio',
    '1532': 'Razer',
    '12D1': 'Huawei',
    '047F': 'Plantronics/Poly',
    '0411': 'MelCo/Buffalo',
    '041E': 'Creative',
    '054C': 'Sony',
    '05A7': 'Bose',
    '0B05': 'ASUS',
    '0ADC': 'Audio-Technica',
    '3302': 'Edifier',
    '2F68': 'Marshall',
    '2516': 'Cooler Master',
    '0572': 'Conexant (audio integrado)',
    '1B3F': 'Generalplus (parlantes genéricos)',
    '20A0': 'Turtle Beach',
    '0D9A': 'Harman/AKG',
    # Cámaras / video
    '046D': 'Logitech',
    '045E': 'Microsoft',
    '1908': 'GEMBIRD',
    '0AC8': 'Z-Star (webcams)',
    '05A3': 'ARC International (webcams)',
    '1B3F': 'Generalplus (webcams)',
    '534D': 'MacroSilicon (capturadoras)',
    # Red / conectividad
    '0B95': 'ASIX (adaptadores Ethernet)',
    '0BDA': 'Realtek',
    '2357': 'TP-Link',
    '148F': 'Ralink/MediaTek',
    '0CF3': 'Qualcomm/Atheros',
    '0A5C': 'Broadcom (Bluetooth)',
    '8087': 'Intel',
    '0E8D': 'MediaTek',
    '7392': 'Edimax',
    '2001': 'D-Link',
    '0846': 'NetGear',
    # Biometría / seguridad
    '1050': 'Yubico (YubiKey)',
    '27A6': 'Feitian (tokens)',
    '096E': 'Feitian (legacy)',
    '1FC9': 'NXP Semiconductors',
    '138A': 'Validity Sensors (huella)',
    '06CB': 'Synaptics (huella)',
    '04F3': 'Elan Microelectronics (huella)',
    # Smartphones / tablets
    '18D1': 'Google',
    '2717': 'Xiaomi',
    '22B8': 'Motorola',
    '04E8': 'Samsung',
    '2A70': 'OnePlus',
    '1004': 'LG',
    '0BB4': 'HTC',
    '19D2': 'ZTE',
    '2C7C': 'Quectel (módems)',
    # Monitores / docks
    '0451': 'Texas Instruments (docks)',
    '17E9': 'DisplayLink',
    '056D': 'EIZO',
    '0764': 'Cyber Power (UPS)',
    '051D': 'APC (UPS)',
    # Otros fabricantes comunes
    '1366': 'SEGGER (programadores)',
    '067B': 'Prolific (serial-USB)',
    '0403': 'FTDI (serial-USB)',
    '10C4': 'Silicon Labs (serial-USB)',
    '2341': 'Arduino',
    '1A86': 'QinHeng (CH340)',
}

# Fabricantes genéricos que no aportan info útil
_FABRICANTES_GENERICOS = {
    '(standard system devices)',
    '(standard usb host controller)',
    '(generic usb hub)',
    'microsoft',
    'compatible usb storage device',
    '',
}


# PIDs USB de receptores Logitech (Unifying, Nano, Lightspeed, Bolt, etc.).
# Fuente: Solaar lib/logitech_receiver/base_usb.py — mismos IDs que el driver Linux hid-logitech-dj.
_LOGITECH_RECEIVER_PIDS = frozenset({
    'C517', 'C518', 'C51A', 'C51B', 'C521', 'C525', 'C526', 'C52B', 'C52E', 'C52F',
    'C531', 'C532', 'C534', 'C535', 'C537', 'C539', 'C53A', 'C53D', 'C53F', 'C541',
    'C545', 'C547', 'C548', 'C54D',
})

# PIDs de receptores inalámbricos de otras marcas comunes (VID → set de PIDs).
# Microsoft Nano Transceiver / Wireless Desktop receivers (VID 045E).
# Rapoo wireless receivers (VID 24AE).
# A4Tech wireless receivers (VID 09DA).
_OTROS_RECEPTORES_PIDS: dict[str, frozenset] = {
    '045E': frozenset({  # Microsoft
        '0745', '0750', '0752', '07A5', '07B2', '0800', '082A', '0922',
        '09B0', '09BA', '09BB', '09BC', '0990', '0991',
    }),
    '24AE': frozenset({  # Rapoo
        '2000', '2001', '2002', '2003', '2004', '2005', '2010', '2011',
        '2012', '2013', '2014', '2015', '2017', '2018',
    }),
    '09DA': frozenset({  # A4Tech
        '9066', '9090', '9033', '90C0', '90C4', 'F613', 'F624',
    }),
}

# Palabras clave que identifican receptores inalámbricos USB (dongles).
# Incluye inglés, español (Windows localizado) y variantes de marcas comunes.
_RECEPTOR_KEYWORDS = [
    # Logitech
    'unifying', 'unifying receiver', 'nano receiver',
    'lightspeed', 'logi bolt', 'bolt receiver',
    # Genéricos inglés
    'receiver', 'wireless receiver', 'rf receiver', 'nano transceiver',
    'transceiver', 'usb receiver', 'nano usb', '2.4g receiver',
    'wireless adapter', 'wireless dongle', 'usb dongle', 'dongle',
    'wireless usb', 'usb wireless', '2.4g wireless',
    # Genéricos español
    'receptor', 'receptor usb', 'usb receptor', 'receptor inalambrico',
    'receptor nano', 'receptor rf', 'receptor inalambrico usb',
    'inalambrico', 'dispositivo inalambrico', 'usb inalambrico',
    'adaptador inalambrico',
    # Frecuencias (aplica a dongles que Windows nombra así)
    '2.4ghz', '2,4ghz', '2.4 ghz', '2,4 ghz',
    # Microsoft
    'nano transceiver v', 'wireless desktop receiver',
    # Rapoo
    'rapoo receiver', 'rapoo wireless',
]


def _es_receptor_inalambrico(nombre: str) -> bool:
    """True si el nombre del dispositivo corresponde a un receptor inalámbrico USB."""
    nombre_norm = _normalizar_para_comparacion(nombre)
    return any(kw in nombre_norm for kw in _RECEPTOR_KEYWORDS)


def _extraer_vid(instance_id: str) -> str | None:
    """Extrae el VID (Vendor ID) del InstanceId USB."""
    match = re.search(r'VID_([0-9A-Fa-f]{4})', instance_id)
    return match.group(1).upper() if match else None


def _extraer_pid(instance_id: str) -> str | None:
    """Extrae el PID (Product ID) del InstanceId USB."""
    match = re.search(r'PID_([0-9A-Fa-f]{4})', instance_id)
    return match.group(1).upper() if match else None


def _es_logitech_receptor_por_pid(instance_id: str) -> bool:
    """True si el InstanceId corresponde a un receptor inalámbrico Logitech."""
    if _extraer_vid(instance_id) != '046D':
        return False
    pid = _extraer_pid(instance_id)
    return bool(pid and pid in _LOGITECH_RECEIVER_PIDS)


def _es_otro_receptor_por_pid(instance_id: str) -> bool:
    """True si el InstanceId corresponde a un receptor inalámbrico de Microsoft, Rapoo o A4Tech."""
    vid = _extraer_vid(instance_id)
    if not vid:
        return False
    pids_marca = _OTROS_RECEPTORES_PIDS.get(vid)
    if not pids_marca:
        return False
    pid = _extraer_pid(instance_id)
    return bool(pid and pid in pids_marca)


def _conexion_por_nombre_dispositivo(nombre: str) -> str | None:
    """
    Si el nombre amigable del PnP ya indica inalámbrico (sin depender del receptor/dongle).
    """
    n = _normalizar_para_comparacion(nombre or "")
    if not n:
        return None
    if "bluetooth" in n or n.startswith("bt "):
        return "bluetooth"
    if any(
        p in n
        for p in (
            "wireless keyboard",
            "wireless mouse",
            "wireless combo",
            "teclado inalambrico",
            "mouse inalambrico",
            "raton inalambrico",
            "combo inalambrico",
            "2.4g keyboard",
            "2.4g mouse",
            "rf keyboard",
            "rf mouse",
        )
    ):
        return "inalambrico_usb"
    return None


_BUS_DESC_INALAMBRICO = (
    'wireless', 'inalambrico', '2.4g', '2.4ghz', 'rf keyboard', 'rf mouse',
    'wireless keyboard', 'wireless mouse', 'wireless combo',
)


def _inferir_conexion(
    instance_id: str,
    vids_receptores: set | None = None,
    nombre_dispositivo: str = "",
    bus_desc: str = "",
) -> str:
    """
    Determina el tipo de conexión a partir del InstanceId del dispositivo.

    Retorna:
      'bluetooth'       — InstanceId empieza con BTHENUM/BTH/BTHHID
      'inalambrico_usb' — PID de receptor conocido, VID compartido con dongle,
                          BusReportedDeviceDescription indica inalámbrico,
                          o nombre PnP indica kit inalámbrico
      'usb'             — USB cableado (o sin información suficiente)
    """
    if not instance_id:
        return _conexion_por_nombre_dispositivo(nombre_dispositivo) or "usb"
    upper = instance_id.upper()
    if upper.startswith(("BTHENUM\\", "BTH\\", "BTHHID\\")):
        return "bluetooth"
    if _es_logitech_receptor_por_pid(instance_id):
        return "inalambrico_usb"
    if _es_otro_receptor_por_pid(instance_id):
        return "inalambrico_usb"
    if vids_receptores:
        vid = _extraer_vid(instance_id)
        if vid and vid in vids_receptores:
            return "inalambrico_usb"
    # BusReportedDeviceDescription — fuente más fiable para genéricos sin nombre reconocible
    if bus_desc:
        bus_norm = _normalizar_para_comparacion(bus_desc)
        if any(kw in bus_norm for kw in _BUS_DESC_INALAMBRICO):
            return "inalambrico_usb"
    por_nombre = _conexion_por_nombre_dispositivo(nombre_dispositivo)
    if por_nombre:
        return por_nombre
    return "usb"


def _resolver_fabricante_por_vid(instance_id: str) -> str | None:
    """Resuelve el nombre del fabricante a partir del VID en el InstanceId USB."""
    if not instance_id:
        return None
    match = re.search(r'VID_([0-9A-Fa-f]{4})', instance_id)
    if match:
        vid = match.group(1).upper()
        return _USB_VENDORS.get(vid)
    return None


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


def _clasificar_hid(nombre: str, clase: str) -> str | None:
    """
    Clasifica un dispositivo HID como 'teclado', 'mouse' o 'otro_hid'.
    Retorna None si no es un dispositivo HID genérico.
    """
    clase_lower = (clase or '').lower()

    # Clases PnP explícitas de Windows
    if clase_lower == 'keyboard':
        return 'teclado'
    if clase_lower == 'mouse':
        return 'mouse'

    # Para HIDClass, inspeccionar el nombre
    if clase_lower == 'hidclass' and _es_hid_generico(nombre):
        nombre_norm = _normalizar_para_comparacion(nombre)
        if any(kw in nombre_norm for kw in ('keyboard', 'teclado', 'kbd')):
            return 'teclado'
        if any(kw in nombre_norm for kw in ('mouse', 'raton', 'pointing')):
            return 'mouse'
        return 'otro_hid'

    return None


def _extraer_marca(dispositivo: dict) -> str:
    """Retorna fabricante si es conocido; si no, intenta usar el nombre del dispositivo."""
    fab = dispositivo.get('fabricante', '—')
    if fab and fab != '—':
        return fab
    nombre = dispositivo.get('nombre', '')
    nombre_norm = _normalizar_para_comparacion(nombre)
    if nombre and not nombre_norm.startswith(('hid', 'usb', 'generic', 'desconocido')):
        # Quitar sufijo genérico si hay uno (ej: "Logitech - HID Keyboard Device" → "Logitech")
        if ' - ' in nombre:
            partes = nombre.split(' - ', 1)
            sufijo_norm = _normalizar_para_comparacion(partes[1])
            if sufijo_norm.startswith(('hid', 'usb', 'generic')):
                return partes[0].strip()
        return nombre
    return '—'


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
        $devs = Get-PnpDevice -PresentOnly |
        Where-Object {
            $_.Status -eq "OK" -and (
                $_.InstanceId -like "*USB*" -or
                $_.InstanceId -like "BTHENUM*" -or
                $_.InstanceId -like "BTH\\*" -or
                $_.InstanceId -like "BTHHID*" -or
                ($_.InstanceId -like "HID\\VID_*" -and $_.Class -in @('Keyboard','Mouse'))
            )
        }
        $devs | ForEach-Object {
            $busDesc = ''
            try {
                $prop = Get-PnpDeviceProperty -InstanceId $_.InstanceId `
                    -KeyName 'DEVPKEY_Device_BusReportedDeviceDescription' `
                    -ErrorAction SilentlyContinue
                if ($prop) { $busDesc = [string]$prop.Data }
            } catch {}
            [PSCustomObject]@{
                FriendlyName = $_.FriendlyName
                Class        = $_.Class
                Manufacturer = $_.Manufacturer
                InstanceId   = $_.InstanceId
                BusDesc      = $busDesc
            }
        } | ConvertTo-Json
        """
        
        resultado = subprocess.run(
            ['powershell', '-NoProfile', '-Command', ps_script],
            capture_output=True,
            text=True,
            encoding='utf-8', errors='replace',
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
                instance_id = dispositivo.get('InstanceId', '')
                bus_desc = dispositivo.get('BusDesc', '') or ''

                # Excluir infraestructura interna
                if _es_dispositivo_excluido(nombre):
                    continue

                # Si el fabricante es genérico, intentar resolver via VID
                if fabricante.lower().strip() in _FABRICANTES_GENERICOS:
                    vid_fabricante = _resolver_fabricante_por_vid(instance_id)
                    if vid_fabricante:
                        fabricante = vid_fabricante

                nombre_final = _normalizar_nombre_usb(nombre, fabricante)

                # Los HID genéricos no se deduplicан: puede haber varios físicamente
                # distintos con el mismo nombre (ej: teclado y mouse ambos = "Dispositivo de entrada USB")
                hid_tipo = _clasificar_hid(nombre, clase)
                if hid_tipo is not None:
                    # Usar contador para permitir múltiples HID genéricos
                    clave = f"{nombre_final}|{clase}|{sum(1 for c in vistos if c.startswith(f'{nombre_final}|{clase}'))}"
                else:
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
                    '_hid_tipo': hid_tipo,
                    '_instance_id': instance_id,
                    '_bus_desc': bus_desc,
                })

            # Detectar receptores inalámbricos USB y recolectar sus VIDs
            # Un receptor con el mismo VID que el teclado/mouse indica que es inalámbrico
            vids_receptores: set[str] = set()
            for raw in datos:
                nombre_raw = raw.get('FriendlyName', '')
                if _es_receptor_inalambrico(nombre_raw):
                    vid = _extraer_vid(raw.get('InstanceId', ''))
                    if vid:
                        vids_receptores.add(vid)

            # Separar teclados, mouses y HID ambiguos
            teclados = [d for d in dispositivos if d.get('_hid_tipo') == 'teclado']
            mouses = [d for d in dispositivos if d.get('_hid_tipo') == 'mouse']
            otros_hid = [d for d in dispositivos if d.get('_hid_tipo') == 'otro_hid']
            otros = [d for d in dispositivos if d.get('_hid_tipo') is None]

            # Limpiar otros_hid: eliminar entradas cuyo VID+PID ya aparece
            # en un teclado o mouse detectado (son la misma pieza física
            # expuesta en distinto nivel PnP: USB\... HIDClass vs HID\... Keyboard/Mouse)
            if (teclados or mouses) and otros_hid:
                vid_pids_km: set[tuple[str | None, str | None]] = set()
                for d in teclados + mouses:
                    iid = d.get('_instance_id', '')
                    vp = (_extraer_vid(iid), _extraer_pid(iid))
                    if vp[0] and vp[1]:
                        vid_pids_km.add(vp)
                if vid_pids_km:
                    otros_hid = [
                        d for d in otros_hid
                        if (_extraer_vid(d.get('_instance_id', '')),
                            _extraer_pid(d.get('_instance_id', ''))) not in vid_pids_km
                    ]

            # Fallback: si hay HID ambiguos pero no se detectó teclado ni mouse,
            # asumir 1ro=teclado, 2do=mouse (combinación más común)
            if otros_hid and not teclados and not mouses:
                if len(otros_hid) >= 1:
                    teclados = [otros_hid[0]]
                if len(otros_hid) >= 2:
                    mouses = [otros_hid[1]]
                otros_hid = otros_hid[2:]

            if teclados:
                n = len(teclados)
                t0 = teclados[0]
                otros.append({
                    'nombre': 'Teclado' + (f' ({n} dispositivos)' if n > 1 else ''),
                    'categoria': 'Teclado',
                    'fabricante': _extraer_marca(t0) if n == 1 else '—',
                    'clase': 'Keyboard',
                    'conexion': _inferir_conexion(
                        t0.get('_instance_id', ''),
                        vids_receptores,
                        t0.get('nombre', ''),
                        t0.get('_bus_desc', ''),
                    ),
                })
            if mouses:
                n = len(mouses)
                m0 = mouses[0]
                otros.append({
                    'nombre': 'Mouse' + (f' ({n} dispositivos)' if n > 1 else ''),
                    'categoria': 'Mouse',
                    'fabricante': _extraer_marca(m0) if n == 1 else '—',
                    'clase': 'Mouse',
                    'conexion': _inferir_conexion(
                        m0.get('_instance_id', ''),
                        vids_receptores,
                        m0.get('nombre', ''),
                        m0.get('_bus_desc', ''),
                    ),
                })
            if otros_hid:
                n = len(otros_hid)
                otros.append({
                    'nombre': 'Controlador HID' + (f' ({n} dispositivos)' if n > 1 else ''),
                    'categoria': 'Controlador HID',
                    'fabricante': '—',
                    'clase': 'HIDClass',
                })

            # Limpiar campos internos
            for d in otros:
                d.pop('_hid_tipo', None)
                d.pop('_instance_id', None)
                d.pop('_bus_desc', None)
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
        'Teclado': '[KB]' if not usar_emoji else '⌨️',
        'Mouse': '[MOU]' if not usar_emoji else '🖱️',
        'Controlador HID': '[HID]' if not usar_emoji else '🎮',
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
        cx = d.get('conexion')
        sufijo_cx = ""
        if cx == "bluetooth":
            sufijo_cx = " [Bluetooth]"
        elif cx == "inalambrico_usb":
            sufijo_cx = " [Inalámbrico USB]"
        elif cx == "usb":
            sufijo_cx = " [USB cableado]"
        if fab and fab != '—' and fab not in nombre:
            lineas.append(f"      • {nombre} ({fab}){sufijo_cx}")
        else:
            lineas.append(f"      • {nombre}{sufijo_cx}")
    
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
            encoding='utf-8', errors='replace',
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