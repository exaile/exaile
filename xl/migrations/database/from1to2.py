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

from gi.repository import Gio


def migrate(db, pdata, oldversion, newversion):
    for k in (x for x in pdata.keys() if x.startswith("tracks-")):
        p = pdata[k]
        tags = p[0]
        try:
            loc = tags['__loc']
        except KeyError:
            continue
        if not loc or not loc.startswith("file://"):
            continue
        loc = loc[7:]
        gloc = Gio.File.new_for_uri(loc)
        uri = gloc.get_uri()
        tags['__loc'] = uri
        pdata[k] = (tags, p[1], p[2])

    if '_serial_libraries' in pdata:
        libs = pdata['_serial_libraries']
        for l in libs:
            l['location'] = Gio.File.new_for_uri(l['location']).get_uri()
        pdata['_serial_libraries'] = libs

    pdata['_dbversion'] = newversion
    pdata.sync()
