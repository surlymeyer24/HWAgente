# -*- mode: python ; coding: utf-8 -*-
# Metadatos de versión en el .exe (Propiedades → Detalles) = config/config.py → VERSION
import os
import re
import sys

_spec_dir = SPECPATH
sys.path.insert(0, _spec_dir)
from config.config import VERSION

def _version_quad(s):
    """'2.2.0' → (2, 2, 0, 0) para el recurso de versión de Windows."""
    nums = [int(x) for x in re.findall(r"\d+", s)]
    while len(nums) < 4:
        nums.append(0)
    return tuple(nums[:4])


_vquad = _version_quad(VERSION)

from PyInstaller.utils.win32.versioninfo import (
    FixedFileInfo,
    StringFileInfo,
    StringStruct,
    StringTable,
    VarFileInfo,
    VarStruct,
    VSVersionInfo,
)

_win_version = VSVersionInfo(
    ffi=FixedFileInfo(
        filevers=_vquad,
        prodvers=_vquad,
        mask=0x3F,
        flags=0x0,
        OS=0x40004,
        fileType=0x1,
        subtype=0x0,
        date=(0, 0),
    ),
    kids=[
        StringFileInfo(
            [
                StringTable(
                    "040904B0",
                    [
                        StringStruct("CompanyName", ""),
                        StringStruct("FileDescription", "AgenteBacar"),
                        StringStruct("FileVersion", VERSION),
                        StringStruct("InternalName", "AgenteBacar"),
                        StringStruct("LegalCopyright", ""),
                        StringStruct("OriginalFilename", "AgenteBacar.exe"),
                        StringStruct("ProductName", "AgenteBacar"),
                        StringStruct("ProductVersion", VERSION),
                    ],
                )
            ]
        ),
        VarFileInfo([VarStruct("Translation", [1033, 1200])]),
    ],
)

a = Analysis(
    ['main.py'],
    pathex=[],
    binaries=[],
    datas=[('auth', 'auth'), ('config', 'config')],
    hiddenimports=[
        'win32timezone',
        'src.core.perifericos',
        'src.core.scanner',
        'src.core.windows_updates',
        'src.core.software_critico',
        'src.core.programas_instalados',
        'src.core.auto_update',
        'src.database.firebase_client',
        'src.core.exe_version',
    ],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
    noarchive=False,
    optimize=0,
)
pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.datas,
    [],
    name='AgenteBacar',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    # UPX puede dejar el recurso de versión del PE ilegible → Windows muestra 1.0.0.0
    upx=False,
    upx_exclude=[],
    runtime_tmpdir=None,
    console=True,  # TEMPORAL — revertir a False antes del release
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    uac_admin=True,
    version=_win_version,
)
