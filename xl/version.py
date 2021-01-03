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

import logging
import os
from typing import Dict

logger = logging.getLogger(__name__)

__version__ = "devel"

# We need the local hack for OSX bundled apps, so we depend on the main script
# to set the environment variable correctly instead of trying to infer an
# absolute path
# exaile_dir = os.path.split(os.path.dirname(os.path.realpath(__file__)))[0]
exaile_dir = os.environ['EXAILE_DIR']


def get_current_version():
    """
    Get the latest version identifier for the branch contained in the
    current directory. Returns None if the directory is not a branch or
    the version identifier cannot be found.
    """
    import subprocess

    try:
        return (
            subprocess.check_output(
                ['git', 'describe', '--tags', '--abbrev=0'], stderr=subprocess.DEVNULL
            )
            .strip()
            .decode('utf-8')
        )
    except (subprocess.CalledProcessError, OSError):
        return None


def get_current_revision():
    """
    Get the latest revision identifier for the branch contained in the
    current directory. Returns None if the directory is not a branch or
    the revision identifier cannot be found.
    """
    import subprocess

    try:
        return (
            subprocess.check_output(
                ['git', 'rev-parse', '--short=7', 'HEAD'], stderr=subprocess.DEVNULL
            )
            .strip()
            .decode('utf-8')
        )
    except (subprocess.CalledProcessError, OSError):
        return None


if "DIST_VERSION" in os.environ:
    __version__ = os.environ['DIST_VERSION']
elif os.path.exists(os.path.join(exaile_dir, ".git")):
    version = get_current_version()
    if version is not None:
        __version__ = version
    revision = get_current_revision()
    if revision is not None:
        __version__ += "+" + revision

__external_versions__: Dict[str, str] = {}


def register(name, version):
    '''Registers versions of external components for diagnostic purposes'''
    if name not in __external_versions__:
        __external_versions__[name] = version
        logger.info("Using %s %s", name, version)
