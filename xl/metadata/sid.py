# Copyright (C) 2008-2010 Adam Olsen
# Copyright (C) 2025 Johannes Sasongko <johannes sasongko org>
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


from xl.metadata._base import BaseFormat


class SidFormat(BaseFormat):
    writable = False

    def load(self):
        with open(self.loc, 'rb') as f:
            # Search for "+16" in
            # https://www.hvsc.c64.org/download/C64Music/DOCUMENTS/SID_file_format.txt
            f.seek(0x16)
            read = lambda: f.read(32).split(b'\0', 1)[0].decode('cp1252', 'replace')
            self.mutagen = {
                'title': read(),
                'artist': read(),
                'copyright': read(),
            }
