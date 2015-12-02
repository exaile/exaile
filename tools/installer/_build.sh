
if [ "$TARGET" == "" ]; then
  TARGET=`pwd`
fi

pushd "$TARGET"

if [ "$SDK_PLATFORM" == "darwin" ]; then
  DIST=_dist_osx
else
  DIST=_dist
fi

EXAILE_DIR="$TARGET"/../..
COPYDIR="$TARGET"/_copy
DESTDIR="$TARGET"/_inst
DISTDIR="$TARGET"/$DIST/exaile
DESTDATADIR="$DESTDIR"/usr/share/exaile/data

for d in _copy _inst _build _build_osx $DIST; do
  [ -d "$d" ] && rm -rf "$d"
done

pushd "$EXAILE_DIR"
git archive HEAD --prefix=_copy/ | tar -x -C tools/installer/
popd

pushd "$COPYDIR"
make
PREFIX=/usr DESTDIR="$DESTDIR" make install

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
  (wine cmd /c _build.bat)
fi

# Copy extra data

cp "$COPYDIR"/COPYING "$DISTDIR"
prune_translations "$DESTDIR"/usr/share/locale "$DISTDIR"

# Run the installer
if [ "$SDK_PLATFORM" == "darwin" ]; then
  prune_translations "$DESTDIR"/usr/share/locale $DIST/Exaile.app/Contents/Resources
  misc/create_dmg.sh $DIST/Exaile.app
else
  package_installer ../exaile_installer.nsi
fi

for d in _copy _inst; do
  [ -d "$d" ] && rm -rf "$d"
done
