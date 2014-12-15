# Copyright (C) 2019 Adam Olsen
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

import xdg

major = "3.4"
minor = "3"
extra = ""

def get_current_revision(directory):
    """
        Get the latest revision identifier for the branch contained in
        'directory'. Returns None if the directory is not a branch or
        the revision identifier cannot be found.
    """
    import subprocess

    try:
        return subprocess.check_output([
            'git', 'rev-parse', '--short=7', 'HEAD'
        ]).strip()
    except subprocess.CalledProcessError:
        return None

if xdg.local_hack:
    revision = get_current_revision(xdg.exaile_dir)
    if revision is not None:
        extra += "+" + revision

__version__ = major + "." + minor + extra
