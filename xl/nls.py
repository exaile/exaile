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
# Foundation, Inc., 675 Mass Ave, Cambridge, MA 02139, USA.
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

import locale, os
from xl import xdg

# set the locale to LANG, or the user's default
locale.setlocale(locale.LC_ALL, None)

try:
    import gettext as gettextmod

    gettextmod.textdomain('exaile')
    if xdg.local_hack: # running from source dir, so we have to set the paths
        gettextmod.bindtextdomain('exaile', os.path.join(xdg.exaile_dir, 'po'))

    gettextfunc = gettextmod.gettext

    def gettext(text):
        return gettextfunc(text).decode("utf-8")

    ngettextfunc = gettextmod.ngettext

    def ngettext(singular, plural, n):
        return ngettextfunc(singular, plural, n).decode('utf-8')

except ImportError:
    # gettext is not available.  Provide a dummy function instead
    def gettext(text):
        return text

    def ngettext(singular, plural, n):
        if n == 1:
            return singular
        else:
            return plural

# vim: et sts=4 sw=4
