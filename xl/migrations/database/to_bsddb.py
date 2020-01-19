# Copyright (C) 2017 Dustin Spicuzza
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

import glob
import logging
import os
import shelve

from xl import common, shelve_compat

logger = logging.getLogger(__name__)


def migrate(path):
    shelve_compat.ensure_shelve_compat()

    bak_path = path + os.extsep + 'tmp'

    try:
        old_shelf = shelve.open(path, 'r', protocol=common.PICKLE_PROTOCOL)
    except Exception:
        logger.warning("%s may be corrupt", path)
        raise

    db = common.bsddb.hashopen(bak_path, 'c')
    new_shelf = shelve.BsdDbShelf(db, protocol=common.PICKLE_PROTOCOL)

    for k, v in old_shelf.items():
        new_shelf[k] = v

    new_shelf.close()
    old_shelf.close()

    try:
        os.replace(bak_path, path)
    except Exception:
        try:
            os.unlink(bak_path)
        except Exception:
            pass
        raise

    # Various types of *dbm modules use more than one file to store the data.
    # Now that we are assured that the migration is complete, delete them if
    # present
    for extra in glob.glob(path + os.extsep + '*'):
        try:
            os.unlink(extra)
        except Exception as e:
            logger.warning("Could not delete %s: %s", extra, e)

    logger.info("Migration successfully completed!")
