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

"""
    This is the Native Language Support module.  It basically allows us to
    code in a gettext fashion without a hard depend on gettext itself.
"""

import sys
import locale
import os

try:
    # Set to user default, gracefully fallback on C otherwise
    locale.setlocale(locale.LC_ALL, '')
except locale.Error, e:
    # Error message copied from bzr
    sys.stderr.write('exaile: Warning: %s\n'
                     '  Exaile could not set the application locale, this\n'
                     '  may cause language-specific problems. To investigate this\n'
                     '  issue, look at the output of the locale tool.\n' % e)

try:
    import gettext as gettextmod

    # Required for gtk.Builder messages
    try:
        locale.textdomain('exaile')
    except AttributeError: # E.g. Windows
        pass
    # Required for dynamically added messages
    gettextmod.textdomain('exaile')

    # If running from source dir, we have to set the paths.
    # (The test is equivalent to xdg.local_hack but without the xdg import,
    # which pulls in glib.)
    if os.path.exists(os.path.join(os.environ['EXAILE_DIR'], 'po')):
        import os.path
        locale_path = os.path.join(os.environ['EXAILE_DIR'], 'po')
        try:
            locale.bindtextdomain('exaile', locale_path)
        except AttributeError: # E.g. Windows
            pass
        gettextmod.bindtextdomain('exaile', locale_path)

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
