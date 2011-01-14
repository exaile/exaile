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
    Allows for playback and queue control
"""

__all__ = [
        'adapters',
        'pipe',
        'queue',
        'engine_normal',
        'engine_unified'
        ]

import gobject
gobject.threads_init()
import logging
import os

from xl import settings, xdg

import queue

logger = logging.getLogger(__name__)

def get_player():
    pname = settings.get_option("player/engine", "normal")
    if pname == "normal":
        logger.debug("Normal playback engine selected.")
        from xl.player.engine_normal import NormalPlayer
        return NormalPlayer
    elif pname == "unified":
        logger.debug("Unified playback engine selected.")
        from xl.player.engine_unified import UnifiedPlayer
        return UnifiedPlayer
    else:
        logger.warning("Couldn't find specified playback engine, "
                "falling back to normal.")
        from xl.player.engine_normal import NormalPlayer
        return NormalPlayer


# TODO: write a better interface than this
PLAYER = get_player()()
QUEUE = queue.PlayQueue(PLAYER,
        location=os.path.join(xdg.get_data_dir(), 'queue.state'))

