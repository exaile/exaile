#!/bin/bash

cd $(dirname "$0")/../..
rm -rf dist/copy

mkdir -p dist
bzr export dist/copy

pushd dist/copy/tools/osx

EXAILE_DIR=`dirname $0`/../..
DIST_VERSION=`EXAILE_DIR=$EXAILE_DIR python2 -c 'import xl.xdg; xl.xdg.local_hack=False; import xl.version; print xl.version.__version__'`

python setup.py py2app

cp ../../README.OSX Exaile/README.txt
ln -s /Applications Exaile/Applications
hdiutil create -srcfolder Exaile Exaile.dmg

popd
mv dist/copy/tools/osx/Exaile.dmg dist/exaile-$DIST_VERSION.dmg

rm -rf dist/copy
