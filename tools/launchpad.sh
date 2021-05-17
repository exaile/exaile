#!/bin/bash -x

PKG_NAME="exaile"
PKG_VERSION="4.1.1"
DEB_VERSION="0ubuntu18"
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

sed -i "s/<#VERSION#>/$VER_STRING/g" debian/changelog

## This happens on launchpad build server
#dpkg-buildpackage
#exit 0;
##

dpkg-source -b .
dpkg-genchanges > $CHANGESFILE
debsign -k Launchpad $CHANGESFILE
dput ppa:luzip665/ppa $CHANGESFILE