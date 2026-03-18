# -*- mode: python ; coding: utf-8 -*-

from pathlib import Path


def collect_tree(source_root: str, dest_root: str):
    source = Path(source_root)
    items = []
    for path in source.rglob("*"):
        if path.is_file():
            relative_parent = path.relative_to(source).parent
            target_dir = str(Path(dest_root) / relative_parent).replace("\\", "/")
            items.append((str(path), target_dir))
    return items


datas = [
    ('assets\\app_icon.png', 'assets'),
]
datas += collect_tree(r'C:\Users\t0kage\AppData\Local\Programs\Python\Python313\tcl\tcl8.6', '_tcl_data')
datas += collect_tree(r'C:\Users\t0kage\AppData\Local\Programs\Python\Python313\tcl\tk8.6', '_tk_data')


a = Analysis(
    ['luma_exr_viewer.py'],
    pathex=[],
    binaries=[],
    datas=datas,
    hiddenimports=[
        'tkinter',
        'tkinter.ttk',
        'tkinter.filedialog',
        'tkinter.messagebox',
        '_tkinter',
    ],
    hookspath=['hooks'],
    hooksconfig={},
    runtime_hooks=['pyi_rth_tk_env.py'],
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
    name='LumaEXR-Viewer_v_1_0',
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
    icon=['assets\\app_icon.ico'],
)
