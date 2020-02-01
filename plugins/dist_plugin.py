# Copyright (C) 2008-2010 Adam Olsen
#
# This program is free software; you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation; either version 2, or (at your option)
# any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program; if not, write to the Free Software
# Foundation, Inc., 51 Franklin Street, Fifth Floor, Boston, MA  02110-1301, USA.
#
#
# The developers of the Exaile media player hereby grant permission
# for non-GPL compatible GStreamer and Exaile plugins to be used and
# distributed together with GStreamer and Exaile. This permission is
# above and beyond the permissions granted by the GPL license by which
# Exaile is covered. If you modify this code, you may extend this
# exception to your version of the code, but you are not obligated to
# do so. If you do not wish to do so, delete this exception statement
# from your version.

# script to turn a plugin dir into a .exz file suitable for distribution

# takes one commandline parameter: the name of the plugin to build, which must
# be a subdirectory of the current directory

# outputs the built plugin to the current directory, overwriting any current
# build of that plugin

import os
import tarfile
from optparse import OptionParser


p = OptionParser()
p.add_option(
    "-c",
    "--compression",
    dest="compression",
    action="store",
    choices=("", "gz", "bz2"),
    default="bz2",
)
p.add_option(
    "-e",
    "--ignore-extension",
    dest="extensions",
    action="append",
    default=(".pyc", ".pyo"),
)
p.add_option("-f", "--ignore-file", dest="files", action="append", default=("test.py"))
p.add_option("-O", "--output", dest="output", action="store", default="")
options, args = p.parse_args()

# allowed values: "", "gz", "bz2"
COMPRESSION = options.compression

# don't add files with these extensions to the archive
IGNORED_EXTENSIONS = options.extensions

# don't add files with this exact name to the archive
IGNORED_FILES = options.files

_ = lambda x: x


for dir in args:

    if not os.path.exists(dir):
        print("No such folder %s" % dir)
        break

    print("Making plugin %s..." % dir)

    if not os.path.exists(os.path.join(dir, "PLUGININFO")):
        print("ERROR: no valid info for %s, skipping..." % dir)
        continue

    f = open(os.path.join(dir, "PLUGININFO"))
    info = {}
    for line in f:
        try:
            key, val = line.split("=", 1)
        except ValueError:
            continue
        key = key.strip()
        val = eval(val)
        info[key] = val
    f.close()

    if "Version" not in info:
        print("ERROR: couldn't get version for %s, skipping..." % dir)
        continue

    tfile = tarfile.open(
        options.output + dir + "-%s.exz" % info["Version"],
        "w:%s" % COMPRESSION,
        format=tarfile.USTAR_FORMAT,
    )

    for fold, subdirs, files in os.walk(dir):
        for file in files:
            stop = False
            for ext in IGNORED_EXTENSIONS:
                if file.endswith(ext):
                    stop = True
                    break
            if stop:
                continue
            for name in IGNORED_FILES:
                if file == name:
                    stop = True
                    break
            if stop:
                continue

            path = os.path.join(fold, file)
            tfile.add(path)

    tfile.close()

print("Done.")
