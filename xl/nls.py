# Copyright (C) 2008-2010 Adam Olsen
# Copyright (C) 2020 Johannes Sasongko <sasongko@gmail.com>
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

"""
    This is the Native Language Support module.  It basically allows us to
    code in a gettext fashion without a hard depend on gettext itself.
"""

import locale
import os.path
import sys
from typing import Optional

try:
    import gettext as gettextmod
except ImportError:
    gettextmod = None


def _get_locale_path() -> Optional[str]:
    # This is the same as xl.xdg.exaile_path. We don't want to import xl.xdg
    # here because it's a heavy import (it pulls in GLib).
    exaile_path = os.environ['EXAILE_DIR']

    # Check if running from source dir
    locale_path = os.path.join(exaile_path, 'build', 'locale')
    if os.path.exists(locale_path):  # Equivalent to xl.xdg.local_hack
        return locale_path

    # Check if installed
    lib_suffix = os.path.join('lib', 'exaile')
    if exaile_path.endswith(lib_suffix):
        prefix = exaile_path[: -len(lib_suffix)]
        locale_path = os.path.join(prefix, 'share', 'locale')
        if os.path.exists(locale_path):
            return locale_path

    return None


def _setup_locale() -> None:
    try:
        # Required for Gtk.Builder messages
        locale.textdomain('exaile')
    except AttributeError:  # E.g. Windows
        pass

    # Required for dynamically added messages
    gettextmod.textdomain('exaile')

    locale_path = _get_locale_path()
    if locale_path is not None:
        try:
            locale.bindtextdomain('exaile', locale_path)
        except AttributeError:  # E.g. Windows
            pass
        gettextmod.bindtextdomain('exaile', locale_path)


try:
    # Set to user default, gracefully fallback on C otherwise
    locale.setlocale(locale.LC_ALL, '')
except locale.Error as e:
    # Error message copied from bzr
    sys.stderr.write(
        'exaile: Warning: %s\n'
        '  Exaile could not set the application locale, this\n'
        '  may cause language-specific problems. To investigate this\n'
        '  issue, look at the output of the locale tool.\n' % e
    )


if gettextmod:
    _setup_locale()
    gettext = gettextmod.gettext
    ngettext = gettextmod.ngettext
else:
    # gettext is not available; provide dummy functions instead

    def gettext(text: str) -> str:
        return text

    def ngettext(singular: str, plural: str, n: float) -> str:
        if n == 1:
            return singular
        else:
            return plural
