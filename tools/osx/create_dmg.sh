#!/bin/bash

set -e

cd $(dirname "$0")/../..
rm -rf dist/copy

mkdir -p dist
git archive HEAD --prefix=copy/ | tar -x -C dist

EXAILE_DIR='.'
PYTHONPATH="/Library/Frameworks/GStreamer.framework/Libraries/python2.7/site-packages/"
DIST_VERSION=`PYTHONPATH=$PYTHONPATH EXAILE_DIR=$EXAILE_DIR python2 -c 'import xl.xdg; xl.xdg.local_hack=False; import xl.version; print xl.version.__version__'`

echo "Building Exaile $DIST_VERSION"

pushd dist/copy/tools/osx

python setup.py py2app

cp ../../README.OSX Exaile/README.txt
ln -s /Applications Exaile/Applications
hdiutil create -srcfolder Exaile Exaile.dmg

popd
mv dist/copy/tools/osx/Exaile.dmg dist/exaile-$DIST_VERSION.dmg

echo "dist/exaile-$DIST_VERSION.dmg created!"

rm -rf dist/copy
