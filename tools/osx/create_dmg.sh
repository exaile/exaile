#!/bin/bash

cd $(dirname "$0")/../..
rm -rf dist/copy

mkdir -p dist
bzr export dist/copy

pushd dist/copy/tools/osx
python setup.py py2app

cp ../../README.OSX Exaile/README.txt
ln -s /Applications Exaile/Applications
hdiutil create -srcfolder Exaile Exaile.dmg

popd
mv dist/copy/tools/osx/Exaile.dmg dist

rm -rf dist/copy
