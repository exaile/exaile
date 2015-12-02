# -*- mode: python -*-

import sys
from PyInstaller.utils.hooks import collect_submodules

if sys.platform == 'win32':
	afile = '_inst/usr/lib/exaile/exaile_win.py'
elif sys.platform == 'darwin':
	afile = '_inst/usr/lib/exaile/exaile_osx.py'
else:
	afile = '_inst/usr/lib/exaile/exaile.py'

block_cipher = None

hiddenimports = collect_submodules('xl') + \
                collect_submodules('xlgui') + \
                collect_submodules('mutagen')

datas =[
  ('_inst/usr/share/exaile/data', ''),
  ('_inst/usr/share/exaile/plugins', ''),
  ('_inst/usr/share/locale', 'share/locale')
]

a = Analysis([afile],
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

if sys.platform == 'darwin':
  app = BUNDLE(coll,
               name='Exaile.app',
               icon="../../data/images/exaile.icns",
               bundle_identifier=None)
