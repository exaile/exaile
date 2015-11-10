
if [ "$TARGET" == "" ]; then
  TARGET=`pwd`
fi

pushd "$TARGET"

EXAILE_DIR="$TARGET"/../..
COPYDIR="$TARGET"/_copy
DESTDIR="$TARGET"/_inst
DISTDIR="$TARGET"/_dist/exaile
DESTDATADIR="$DESTDIR"/usr/share/exaile/data

for d in _copy _inst _build _dist; do
  [ -d "$d" ] && rm -rf "$d"
done

pushd "$EXAILE_DIR"
git archive HEAD --prefix=_copy/ | tar -x -C tools/win-installer/
popd

pushd "$COPYDIR"
make
PREFIX=/usr DESTDIR="$DESTDIR" make install

# Copy things that the unix install doesn't require..
cp exaile_win.py "$DESTDIR"/usr/lib/exaile
cp -r data/config "$DESTDATADIR"
cp data/images/exaile.ico "$DESTDATADIR"/images

popd

find "$DESTDIR" -name '*.pyc' -delete
find "$DESTDIR" -name '*.pyo' -delete

# do pyinstaller thing here
(wine cmd /c _build.bat)

# Copy extra data
copy_pygi_data "$TARGET"/_dist/exaile "$TARGET"/_inst/usr/share/locale
cp "$COPYDIR"/COPYING "$DISTDIR"

# Run the installer
package_installer ../exaile_installer.nsi

for d in _copy _inst; do
  [ -d "$d" ] && rm -rf "$d"
done
