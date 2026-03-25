"""
Lee la cadena FileVersion del PE (misma que Propiedades → Detalles en el .exe).
Solo Windows. Usado en modo frozen para alinear version_agente con el ejecutable real.
"""
from __future__ import annotations

import ctypes
import sys
from ctypes import wintypes


def pe_file_version_string(exe_path: str) -> str | None:
    if sys.platform != "win32" or not exe_path:
        return None
    try:
        dw = wintypes.DWORD(0)
        size = ctypes.windll.version.GetFileVersionInfoSizeW(exe_path, ctypes.byref(dw))
        if not size:
            return None
        buf = ctypes.create_string_buffer(size)
        if not ctypes.windll.version.GetFileVersionInfoW(exe_path, 0, size, buf):
            return None
        ulen = ctypes.c_uint(0)
        p_trans = ctypes.c_void_p()
        if not ctypes.windll.version.VerQueryValueW(
            buf, r"\VarFileInfo\Translation", ctypes.byref(p_trans), ctypes.byref(ulen)
        ):
            return None
        if ulen.value < 4:
            return None
        n = ulen.value // 4
        arr = ctypes.cast(p_trans, ctypes.POINTER(wintypes.DWORD))
        for i in range(n):
            lang_cp = arr[i]
            lang = lang_cp & 0xFFFF
            cp = (lang_cp >> 16) & 0xFFFF
            hexblock = f"{lang:04x}{cp:04x}"
            sub = f"\\StringFileInfo\\{hexblock}\\FileVersion"
            plen = ctypes.c_uint(0)
            pstr = ctypes.c_void_p()
            if ctypes.windll.version.VerQueryValueW(buf, sub, ctypes.byref(pstr), ctypes.byref(plen)):
                if pstr and plen.value:
                    s = ctypes.wstring_at(pstr)
                    if s and s.strip():
                        return s.strip()
        return None
    except Exception:
        return None
