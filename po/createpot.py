#!/bin/sh

intltool-extract --type=gettext/glade exaile.glade &&
xgettext -k_ -kN_ -o messages.pot *.py xl/*.py exaile.glade.h \
    plugins/plugins.glade &&
echo -e "Now edit messages.pot, save it as <locale>.po, and send it to" \
    "arolsen@gmail.com.\nThanks!\n"
