set -e

# We add the bin dirs from the build root to the PATH, because there
# are a lot of instances in the legacy code where we make assumptions
# about where the programs are (e.g. help2man)
init_env

if [ "$TARGET" == "" ]; then
  TARGET=`pwd`
fi

pushd "$TARGET"

if [ "$SDK_PLATFORM" == "darwin" ]; then
  DIST=_dist_osx
else
  DIST=_dist
fi

function build_git {
  "${BUILD_ROOT}"/usr/bin/git.exe "$@"
}

function build_tar {
  "${BUILD_ROOT}"/usr/bin/tar.exe "$@"
}

function build_make {
  "${BUILD_ROOT}"/usr/bin/make.exe "$@"
}

EXAILE_DIR="$TARGET"/../..
COPYDIR="$TARGET"/_copy
DESTDIR="$TARGET"/_inst
DISTDIR="$TARGET"/$DIST/exaile
DESTDATADIR="$DESTDIR"/usr/share/exaile/data

for d in _copy _inst _build _build_osx $DIST; do
  [ -d "$d" ] && rm -rf "$d"
done

pushd "$EXAILE_DIR"
build_git archive HEAD --prefix=_copy/ | build_tar -x -C tools/installer/
if [[ -n "$DIST_VERSION" ]]; then
  sed --in-place "s|__version__ = \"devel\"|__version__ = \"$DIST_VERSION\"|" "$COPYDIR"/xl/version.py
fi
popd

pushd "$COPYDIR"
# Our Makefile relies on $PYTHON3_CMD to run Python commands
export PYTHON3_CMD="${BUILD_ROOT}"/"${MINGW}"/bin/"${PYTHON_ID}".exe
build_make compile locale
build_make install PREFIX=/usr DESTDIR="$DESTDIR"

# Copy things that the unix install doesn't require..
if [ "$SDK_PLATFORM" == "darwin" ]; then
  cp exaile_osx.py "$DESTDIR"/usr/lib/exaile
else
  cp exaile_win.py "$DESTDIR"/usr/lib/exaile
  cp data/images/exaile.ico "$DESTDATADIR"/images
fi

cp -r data/config "$DESTDATADIR"

popd

find "$DESTDIR" -name '*.pyc' -delete
find "$DESTDIR" -name '*.pyo' -delete

# do pyinstaller thing here
if [ "$SDK_PLATFORM" == "darwin" ]; then
  pyinstaller -w --clean --distpath $DIST --workpath _build_osx exaile.spec
else
  build_python -m PyInstaller --clean --distpath _dist --workpath _build --paths ./_inst/usr/lib/exaile exaile.spec
fi

# Copy extra data
cp "$COPYDIR"/COPYING "$DISTDIR"
prune_translations "$DESTDIR"/usr/share/locale "$DISTDIR"


# Run the installer
if [ "$SDK_PLATFORM" == "darwin" ]; then
  prune_translations "$DESTDIR"/usr/share/locale $DIST/Exaile.app/Contents/Resources
  misc/create_dmg.sh $DIST/Exaile.app
else
  package_installer "$TARGET"/exaile_installer.nsi
fi
