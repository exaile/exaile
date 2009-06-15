# Copyright (C) 2008-2009 Adam Olsen 
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

__all__ = [
        'pipe', 
        'queue', 
        'engine_normal',
        'engine_unified'
        ]

import gobject
gobject.threads_init()

from xl.nls import gettext as _
from xl import settings
import logging
logger = logging.getLogger(__name__)

def get_player():
    pname = settings.get_option("player/engine", "normal")
    if pname == "normal":
        logger.debug(_("Normal playback engine selected."))
        from xl.player.engine_normal import NormalPlayer
        return NormalPlayer
    elif pname == "unified":
        logger.debug(_("Unified playback engine selected."))
        from xl.player.engine_unified import UnifiedPlayer
        return UnifiedPlayer
    else:
        logger.warning("Couldn't find specified playback engine, "
                "falling back to normal.")
        return GSTPlayer

