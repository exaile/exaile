#!/bin/sh

set -e

THISDIR=`dirname $0`
EXAILE_DIR="$THISDIR"/..
DIST_VERSION=`EXAILE_DIR=$EXAILE_DIR python2 -c 'import xl.xdg; xl.xdg.local_hack=False; import xl.version; print xl.version.__version__'` 

if ! "$THISDIR"/plugin_tool.py check; then
    if [ -z "$EXAILE_IGNORE_PLUGINS" ]; then
        echo "Plugin version check failed, set environment variable EXAILE_IGNORE_PLUGINS=1 to ignore"
        exit 1
    fi
fi

#if [ ! -f "tools/installer/build_win32_installer.sh" ]; then
#  echo "python-gtk3-gst-sdk links not installed (use create_links.sh)! Cannot build windows installer"
#  exit 1
#fi

echo "Creating distribution for Exaile $DIST_VERSION"

tar --gzip --format=posix --owner 0 --group 0 \
    -cf dist/exaile-${DIST_VERSION}.tar.gz dist/copy \
    --exclude=dist/copy/.git* \
    --transform s/dist\\/copy/exaile-${DIST_VERSION}/

#
# See tools/installer/README.md for instructions
#

#echo "Generating Windows installer via python-gtk3-gst-sdk"

#pushd tools/installer
#./build_win32_installer.sh

#if [ "$?" != "0" ]; then
#    echo "Warning: the win32 installer build seems to have failed..."
#fi

#popd 

#mv tools/installer/exaile-LATEST.exe dist/exaile-${DIST_VERSION}.exe

echo "Successfully built exaile installer! Going to sign the resulting packages"
echo "with gpg (feel free to CTRL-C at this point if you don't care about that)"

gpg --armor --sign --detach-sig dist/exaile-${DIST_VERSION}.tar.gz
#gpg --armor --sign --detach-sig dist/exaile-${DIST_VERSION}.exe
