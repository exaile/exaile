# -*- mode: python -*-

import sys
import pathlib
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
    + collect_submodules('pynput')
    + collect_submodules('pylast')
)

binaries = []

if sys.platform == 'win32':
    # In msys2/mingw32 GStreamer 1.22.1, the `soup` plugin (used for playing
    # radio streams) is not linked against the `libsoup-*.dll` DLL, so
    # PyInstaller's dependency analysis fails to pick up the DLL, and we need
    # to manually pass it via `binaries`.
    # Due to an oversight in PyInstaller, manually-passed `binaries` are not
    # subjected to dependency analysis, so we also need to ensure that missing
    # dependencies of `libsoup-*.dll` are collected. One such dependency is
    # `libsqlite3-*.dll`.
    dll_dir = pathlib.Path('_build_root/mingw32/bin')
    dll_patterns = [
        # match `libsoup-2.4-1.dll` but not `libsoup-gnome-2.4-1.dll`
        'libsoup-[0-9]*.dll',
        # dependency of `libsoup`
        'libsqlite3-[0-9]*.dll',
    ]
    for dll_pattern in dll_patterns:
        for dll_name in dll_dir.glob(dll_pattern):
            binaries += [(str(dll_name), '.')]

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
