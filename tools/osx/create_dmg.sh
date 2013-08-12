#!/bin/bash

cd $(dirname "$0")
rm -rf build Exaile Exaile.dmg

python setup.py py2app

cp README.txt Exaile
hdiutil create -srcfolder Exaile Exaile.dmg