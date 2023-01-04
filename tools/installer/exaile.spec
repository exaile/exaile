# -*- mode: python -*-

import sys
from PyInstaller.utils.hooks import collect_submodules

if sys.platform == 'win32':
    entry_point_script = '_inst/usr/lib/exaile/exaile_win.py'
elif sys.platform == 'darwin':
    entry_point_script = '_inst/usr/lib/exaile/exaile_osx.py'
else:
    entry_point_script = '_inst/usr/lib/exaile/exaile.py'

hiddenimports = (
    collect_submodules('xl')
    + collect_submodules('xlgui')
    + collect_submodules('keyboard')
    + collect_submodules('feedparser')
    + collect_submodules('musicbrainzngs')
    + collect_submodules('mutagen')
    + collect_submodules('pylast')
)

binaries = []

# We don't use packaging directly, but this is required because something else
# uses it and PyInstaller (tested with v3.4) fails to detect some of
# packaging's subpackages.
hiddenimports += collect_submodules('packaging')

datas = [
    ('_inst/usr/share/exaile/data', 'data'),
    ('_inst/usr/share/exaile/plugins', 'plugins'),
    ('_inst/usr/share/locale', 'share/locale'),
]

gst_exclude_plugins = [
    'aom',
    'assrender',
    'cacasink',
    'daala',
    'dvdread',
    'dvdsub',
    'faac',
    'mxf',
    'openal',
    'openexr',
    'opengl',
    'openh264',
    'opencv',
    'resindvd',
    'rtmp*',
    'schro',
    'video*',
    'vpx',
    'wasapi',  # Generally buggy, e.g. https://github.com/exaile/exaile/issues/532
    'webp',
    'webrtc*',
    'x264',
    'x265',
    'xvimage',
    'zbar',
]

a = Analysis(
    [entry_point_script],
    pathex=['_inst/usr/lib/exaile'],
    binaries=binaries,
    datas=datas,
    hiddenimports=hiddenimports,
    excludes=['_tkinter', 'tkinter'],
    hooksconfig={
        "gstreamer": {
            "exclude_plugins": gst_exclude_plugins,
        },
    },
)

pyz = PYZ(
    a.pure,
    a.zipped_data,
)

exe = EXE(
    pyz,
    a.scripts,
    exclude_binaries=True,
    name='exaile',
    debug=False,
    strip=False,
    upx=True,
    console=False,
)

coll = COLLECT(
    exe,
    a.binaries,
    a.zipfiles,
    a.datas,
    strip=False,
    upx=True,
    name='exaile',
)

if sys.platform == 'darwin':
    app = BUNDLE(
        coll,
        name='Exaile.app',
        icon="../../data/images/exaile.icns",
        bundle_identifier=None,
    )
