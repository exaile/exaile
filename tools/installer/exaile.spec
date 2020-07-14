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
                collect_submodules('keyboard') + \
                collect_submodules('feedparser') + \
                collect_submodules('musicbrainzngs') + \
                collect_submodules('mutagen') + \
                collect_submodules('pylast')

binaries = []

# We don't use packaging directly, but this is required because something else
# uses it and PyInstaller (tested with v3.4) fails to detect some of
# packaging's subpackages.
hiddenimports += collect_submodules('packaging')

datas =[
  ('_inst/usr/share/exaile/data', 'data'),
  ('_inst/usr/share/exaile/plugins', 'plugins'),
  ('_inst/usr/share/locale', 'share/locale')
]

# Make sure we bundle the gspawn-*-helper.exe executable,
# which is required for opening hyperlinks on Windows:
# https://github.com/exaile/exaile/issues/712
if True:
    from PyInstaller.compat import is_win

    if is_win:
        import glob
        from PyInstaller.utils.hooks import get_gi_libdir

        libdir = get_gi_libdir('GLib', '2.0')
        pattern = os.path.join(libdir, 'gspawn-*-helper.exe')
        for f in glob.glob(pattern):
            binaries.append( (f, '.') )

# requires https://github.com/pyinstaller/pyinstaller/pull/3608
def assemble_hook(analysis):
    # filter out gstreamer plugins we don't want
    to_remove = [
      'gstaom',
      'gstassrender',
      'gstcacasink',
      'gstdaala',
      'gstdvdread',
      'gstdvdsub',
      'gstfaac',
      'gstmxf',
      'gstopenal',
      'gstopenexr',
      'gstopengl',
      'gstopenh264',
      'gstopencv',
      'gstresindvd',
      'gstrtmp',
      'gstschro',
      'gstvideo',
      'gstvpx',
      'gstwasapi',  # Generally buggy, e.g. https://github.com/exaile/exaile/issues/532
      'gstwebp',
      'gstwebrtc',
      'gstx264',
      'gstx265',
      'gstxvimage',
      'gstzbar',
    ]
    
    def _exclude(b):
        for r in to_remove:
            if r in b and 'libgstvideo-1' not in b:
                print("Excluding", b)
                return True
        return False
    
    analysis.binaries = [
      b for b in analysis.binaries if not _exclude(b[0])
    ]

a = Analysis([afile],
             pathex=['_inst/usr/lib/exaile'],
             binaries=binaries,
             datas=datas,
             hiddenimports=hiddenimports,
             hookspath=[],
             runtime_hooks=[],
             excludes=['tcl', 'tk', '_tkinter', 'tkinter', 'Tkinter'],
             win_no_prefer_redirects=False,
             win_private_assemblies=False,
             cipher=block_cipher,
             assemble_hook=assemble_hook)

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
