import hashlib
import json
import re
import subprocess
import time


_CACHE = {"data": None, "ts": 0.0}

_PS_SCRIPT = r"""
$paths = @(
    @{ Ruta = 'HKLM:\SOFTWARE\Microsoft\Windows\CurrentVersion\Uninstall\*';              Arch = 'x64'  },
    @{ Ruta = 'HKLM:\SOFTWARE\WOW6432Node\Microsoft\Windows\CurrentVersion\Uninstall\*';  Arch = 'x86'  },
    @{ Ruta = 'HKCU:\SOFTWARE\Microsoft\Windows\CurrentVersion\Uninstall\*';              Arch = 'user' }
)
$resultado = @()
foreach ($p in $paths) {
    Get-ItemProperty -Path $p.Ruta -ErrorAction SilentlyContinue | ForEach-Object {
        $nombre = $_.DisplayName
        if (-not $nombre) { return }
        if ($_.SystemComponent -eq 1) { return }
        if ($_.ParentKeyName) { return }
        $version = $_.DisplayVersion
        if ($_.WindowsInstaller -eq 1 -and -not $version) { return }
        $resultado += [PSCustomObject]@{
            Nombre           = $nombre
            Version          = $version
            Publisher        = $_.Publisher
            FechaInstalacion = $_.InstallDate
            Arquitectura     = $p.Arch
        }
    }
}
$resultado | ConvertTo-Json -Compress
"""


def _parsear_fecha_instalacion(valor):
    """Windows guarda InstallDate como 'YYYYMMDD'. Devuelve 'YYYY-MM-DD' o ''."""
    if not valor:
        return ""
    s = str(valor).strip()
    if len(s) == 8 and s.isdigit():
        return f"{s[0:4]}-{s[4:6]}-{s[6:8]}"
    return s


def slug_programa(nombre):
    """Slug estable para ID en subcolección Firestore; el mismo nombre siempre produce el mismo slug."""
    if not nombre:
        return ""
    base = re.sub(r"[^a-z0-9]+", "-", nombre.lower()).strip("-")[:100]
    h = hashlib.md5(nombre.encode("utf-8")).hexdigest()[:8]
    return f"{base}-{h}" if base else h


def _escanear():
    try:
        resultado = subprocess.run(
            ["powershell", "-NoProfile", "-Command", _PS_SCRIPT],
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=60,
            creationflags=subprocess.CREATE_NO_WINDOW,
        )
        if resultado.returncode != 0 or not resultado.stdout.strip():
            return []
        datos = json.loads(resultado.stdout)
        if isinstance(datos, dict):
            datos = [datos]
    except (json.JSONDecodeError, subprocess.TimeoutExpired, Exception):
        return []

    programas = []
    vistos = set()
    for p in datos:
        nombre = (p.get("Nombre") or "").strip()
        if not nombre:
            continue
        slug = slug_programa(nombre)
        if slug in vistos:
            continue
        vistos.add(slug)
        programas.append({
            "nombre": nombre,
            "version": (p.get("Version") or "").strip(),
            "publisher": (p.get("Publisher") or "").strip(),
            "fecha_instalacion": _parsear_fecha_instalacion(p.get("FechaInstalacion")),
            "arquitectura": (p.get("Arquitectura") or "").strip(),
        })
    programas.sort(key=lambda x: x["nombre"].lower())
    return programas


def obtener_programas_instalados(max_edad_seg=3600):
    """Devuelve lista cacheada 60 min; evita reescanear el registro en cada sync."""
    ahora = time.time()
    if _CACHE["data"] is not None and ahora - _CACHE["ts"] < max_edad_seg:
        return _CACHE["data"]
    resultado = _escanear()
    if resultado:
        _CACHE["data"] = resultado
        _CACHE["ts"] = ahora
    return resultado
