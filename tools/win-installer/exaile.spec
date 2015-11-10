# -*- mode: python -*-

from PyInstaller.utils.hooks import collect_submodules

block_cipher = None

hiddenimports = collect_submodules('xl') + \
                collect_submodules('xlgui') + \
                collect_submodules('mutagen')

datas =[
  ('_inst/usr/share/exaile/data', ''),
  ('_inst/usr/share/exaile/plugins', '')
]

a = Analysis(['_inst/usr/lib/exaile/exaile_win.py'],
             pathex=['_inst/usr/lib/exaile'],
             binaries=None,
             datas=datas,
             hiddenimports=hiddenimports,
             hookspath=[],
             runtime_hooks=[],
             excludes=[],
             win_no_prefer_redirects=False,
             win_private_assemblies=False,
             cipher=block_cipher)
pyz = PYZ(a.pure, a.zipped_data,
             cipher=block_cipher)
exe = EXE(pyz,
          a.scripts,
          exclude_binaries=True,
          name='exaile',
          debug=False,
          strip=False,
          upx=True,
          console=False )
coll = COLLECT(exe,
               a.binaries,
               a.zipfiles,
               a.datas,
               strip=False,
               upx=True,
               name='exaile')
