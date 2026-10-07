# -*- mode: python ; coding: utf-8 -*-


a = Analysis(
    ['face_guard.py'],
    pathex=[],
    binaries=[],
    datas=[('C:\\Users\\15945\\AppData\\Local\\Programs\\Python\\Python314\\Lib\\site-packages\\cv2\\data\\haarcascade_frontalface_default.xml', '.'),
           ('assets', 'assets')],
    hiddenimports=[],
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
    name='FaceGuard',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    upx_exclude=[],
    runtime_tmpdir=None,
    console=False,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
)
