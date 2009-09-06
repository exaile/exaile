#!/bin/sh

DIST_VERSION=`grep __version__ dist/copy/xl/main.py | head -n1 | cut -d \' -f 2` 

tar --gzip --format=posix --owner 0 --group 0 \
    -cf dist/exaile-$DIST_VERSION.tar.gz dist/copy \
    --exclude=dist/copy/.bzr* \
    --transform s/dist\\/copy/exaile-$DIST_VERSION/

gpg --armor --sign --detach-sig dist/exaile-$DIST_VERSION.tar.gz
