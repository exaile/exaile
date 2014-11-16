#!/bin/sh

EXAILE_DIR=`dirname $0`/..
DIST_VERSION=`EXAILE_DIR=$EXAILE_DIR python2 -c 'import xl.xdg; xl.xdg.local_hack=False; import xl.version; print xl.version.__version__'` 

echo "Creating distribution for Exaile $DIST_VERSION"

tar --gzip --format=posix --owner 0 --group 0 \
    -cf dist/exaile-${DIST_VERSION}.tar.gz dist/copy \
    --exclude=dist/copy/.git* \
    --transform s/dist\\/copy/exaile-${DIST_VERSION}/

gpg --armor --sign --detach-sig dist/exaile-${DIST_VERSION}.tar.gz

#
# See tools/win-installer/README on how to install NSIS so this part works
#

echo "Generating Windows installer via Wine+NSIS"

wine "C:/Program Files (x86)/NSIS/makensis.exe" tools/win-installer/exaile_installer.nsi
mv tools/win-installer/exaile-LATEST.exe dist/exaile-${DIST_VERSION}.exe

gpg --armor --sign --detach-sig dist/exaile-${DIST_VERSION}.exe
