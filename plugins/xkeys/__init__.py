# Copyright (C) 2006 Adam Olsen
#
# This program is free software; you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation; either version 1, or (at your option)
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

from xl import event

KEYS = None
EXAILE = None
SIGNALS = []

def enable(exaile):
    if exaile.loading:
        event.add_callback(_enable, 'exaile_loaded')
    else:
        _enable(None, exaile, None)

def play_pause(*e):
    exaile = EXAILE
    if exaile.player.is_paused() or exaile.player.is_playing():
        exaile.player.toggle_pause()
    else:
        exaile.queue.play()

def _enable(type, exaile, nothing):
    global KEYS, EXAILE, SIGNALS

    EXAILE = exaile

    try:
        import mmkeys
    except ImportError:
        raise NotImplementedError('mmkeys.so is not available')
        return False

    if not KEYS:
        keys = mmkeys.MmKeys()
    else: keys = KEYS

    s1 = keys.connect('mm_playpause', play_pause)
    s2 = keys.connect('mm_next', lambda *e: exaile.queue.next())
    s3 = keys.connect('mm_prev', lambda *e: exaile.queue.prev())
    s4 = keys.connect('mm_stop', lambda *e: exaile.player.stop())
    SIGNALS += [s1, s2, s3, s4]

    # this is basically here to keep a reference around so that the object
    # doesn't get GCed.  Don't EVER assign KEYS to None, even in disable(), or
    # you'll get a nice segfault when pressing one of the mmkeys
    KEYS = keys

def disable(exaile):
    global SIGNALS

    # DO NOT ASSIGN KEYS to None in this function, unless you like segfaults

    if KEYS:
        for id in SIGNALS:
            KEYS.disconnect(id)

    SIGNALS = []
