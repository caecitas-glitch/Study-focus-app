# -*- mode: python ; coding: utf-8 -*-


a = Analysis(
    ['A:\\Study app\\Focus_app.pyw'],
    pathex=['A:\\Study app'],
    binaries=[],
    datas=[
        ('A:\\Study app\\mobile_companion\\focusflow-companion.apk', 'mobile_companion'),
    ],
    hiddenimports=[
        'flask',
        'werkzeug',
        'jinja2',
        'psutil',
        'mobile_companion',
        'mobile_companion.sync_bridge',
        'mobile_companion.sync_bridge.bridge_server',
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
    name='focus_app',
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
