# Moodbar -  Replace standard progress bar with moodbar
# Copyright (C) 2010  Solyianov Michael <crantisz@gmail.com>
#
# this program is free software; you can redistribute it and/or modify
# it under the terms of the gnu general public license as published by
# the free software foundation; either version 3, or (at your option)
# any later version.
#
# this program is distributed in the hope that it will be useful,
# but without any warranty; without even the implied warranty of
# merchantability or fitness for a particular purpose.  see the
# gnu general public license for more details.
#
# you should have received a copy of the gnu general public license
# along with this program; if not, write to the free software
# foundation, inc., 675 mass ave, cambridge, ma 02139, usa.



import os
from xlgui.preferences import widgets
from xl import xdg
from xl.nls import gettext as _


name = _('Moodbar')
basedir = os.path.dirname(os.path.realpath(__file__))
ui = os.path.join(basedir, "moodbarprefs_pane.ui")


class defaultstyle(widgets.CheckPreference):
    default = False
    name = 'plugin/moodbar/defaultstyle'

class flat(widgets.CheckPreference):
    default = False
    name = 'plugin/moodbar/flat'

class theme(widgets.CheckPreference):
    default = False
    name = 'plugin/moodbar/theme'

class color(widgets.ColorButtonPreference):
    default =  '#AAAAAA'
    name = 'plugin/moodbar/color'


class cursor(widgets.CheckPreference):
    default = False
    name = 'plugin/moodbar/cursor'
class darkness(widgets.ScalePreference):
    default = 1
    name = 'plugin/moodbar/darkness'

