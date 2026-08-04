# PyInstaller spec for EIS Emulator
# Build: cd sim && pyinstaller eis_emulator.spec
# Output: sim/dist/EIS_Emulator.exe

import os
block_cipher = None

SIM_DIR = os.path.dirname(os.path.abspath(SPEC))
GUI_DIR = os.path.join(SIM_DIR, '..', 'gui')

a = Analysis(
    [os.path.join(SIM_DIR, 'run_simulator.py')],
    pathex=[SIM_DIR, GUI_DIR],
    binaries=[],
    datas=[
        # Bundle the pre-exported KiCad schematic SVG
        (os.path.join(SIM_DIR, 'pcb5_schematic.svg'), '.'),
    ],
    hiddenimports=[
        # PyQt5 SVG support (loaded dynamically inside SchematicDialog)
        'PyQt5.QtSvg',
        'PyQt5.sip',
        # Matplotlib Qt5 backend
        'matplotlib.backends.backend_qt5agg',
        'matplotlib.backends.backend_agg',
        # GUI modules imported via dynamic sys.path in dut_panel.py
        'config_panel',
        'data_model',
        'plot_widget',
        'serial_worker',
    ],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=['tkinter', 'scipy', 'pandas'],
    win_no_prefer_redirects=False,
    win_private_assemblies=False,
    cipher=block_cipher,
    noarchive=False,
)

pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.zipfiles,
    a.datas,
    [],
    name='EIS_Emulator',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,          # UPX can break PyQt5 DLLs on some systems
    runtime_tmpdir=None,
    console=False,      # no black console window — pure GUI app
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon=None,
)
