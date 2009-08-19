#!/bin/sh

msgmerge -o - $1 messages.pot | msgfmt -c -o $(echo "$1" | sed s/.po/.mo/ -) -
