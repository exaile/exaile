#!/bin/sh

outpath=$(echo "$1" | sed "s/.po/\/LC_MESSAGES/" -)
mkdir -p $outpath
msgmerge -o - $1 messages.pot | msgfmt -c -o $outpath/exaile.mo -
