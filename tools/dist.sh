#!/bin/sh

DIST_VERSION=`python -c 'import xl.xdg; xl.xdg.local_hack=False; import xl.version; print ".".join((xl.version.major, xl.version.minor))+xl.version.extra'` 

tar --gzip --format=posix --owner 0 --group 0 \
    -cf dist/exaile-${DIST_VERSION}.tar.gz dist/copy \
    --exclude=dist/copy/.bzr* \
    --transform s/dist\\/copy/exaile-${DIST_VERSION}/

gpg --armor --sign --detach-sig dist/exaile-${DIST_VERSION}.tar.gz
