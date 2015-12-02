#!/bin/bash
#
# This has to be run from within the jhbuild shell
#

SDK_PLATFORM="darwin"

function prune_translations {
    # TODO
    misc/prune_translations.py "$1" "$2"/share/locale
}

source _build.sh
