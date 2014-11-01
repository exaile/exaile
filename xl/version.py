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
minor = "1"
extra = ""

def get_latest_bzr_revno(directory):
    """
        Get the latest bzr revision number for the branch contained in
        'directory'. Returns None if the directory is not a branch or
        the revision number cannot be found.
    """
    try:
        import bzrlib.workingtree
        import bzrlib.errors as errors
    except ImportError:
        return None

    try:
        wt = bzrlib.workingtree.WorkingTree.open_containing(directory)[0]
        wt.lock_read()
    except (errors.NoWorkingTree,
            errors.NotLocalUrl,
            errors.NotBranchError,
            errors.LockContention,
            errors.ConnectionError, # --> Only happens on lightweight checkout.
            ):
        return None

    revid = wt.last_revision()
    try:
        revno = wt.branch.revision_id_to_dotted_revno(revid)
    except errors.NoSuchRevision:
        pass
    finally:
        wt.unlock()

    return ".".join(str(n) for n in revno)


if xdg.local_hack:
    revision = get_latest_bzr_revno(xdg.exaile_dir)
    if revision is not None:
        extra += "+bzr" + revision

__version__ = major + "." + minor + extra
