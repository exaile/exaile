#!/bin/bash

PKG_NAME="exaile"
PKG_VERSION="4.1.1"
DEB_VERSION="0ubuntu13"
ARCH="all"

TMP_DIR="/tmp/ex_build/"
PKG_DIR="${PKG_NAME}_${PKG_VERSION}-${DEB_VERSION}_${ARCH}"
VER_STRING="${PKG_VERSION}-${DEB_VERSION}"

export DESTDIR=$TMP_DIR$PKG_DIR

CHANGESFILE="${DESTDIR}.changes"

rm -rf "${TMP_DIR}"
mkdir -p $DESTDIR

cd ..
cp -r * $DESTDIR

cd $DESTDIR
cp -r tools/debian .

cat debian/changelog | sed "s/<#VERSION#>/$VER_STRING/g" > debian/changelog1
cat debian/control   | sed "s/<#VERSION#>/$VER_STRING/g" > debian/control1
rm debian/changelog
rm debian/control
mv debian/changelog1 debian/changelog
mv debian/control1 debian/control

cp debian/readme README

## This happens on launchpad build server
# dpkg-buildpackage
#
##

dpkg-source -b .
dpkg-genchanges > $CHANGESFILE
debsign -k Launchpad $CHANGESFILE
dput ppa:luzip665/ppa $CHANGESFILE