# Moodbar -  Replace standard progress bar with moodbar
# Copyright (C) 2009-2010  Solyianov Michael <crantisz@gmail.com>
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

class CursorPreference(widgets.CheckPreference):
    default = False
    name = 'plugin/moodbar/cursor'

class DarknessPreference(widgets.ScalePreference, widgets.CheckConditional):
    default = 1
    name = 'plugin/moodbar/darkness'
    condition_preference_name = 'plugin/moodbar/cursor'

    def __init__(self, preferences, widget):
        widgets.ScalePreference.__init__(self, preferences, widget)
        widgets.CheckConditional.__init__(self)

class DefaultStylePreference(widgets.CheckPreference):
    default = False
    name = 'plugin/moodbar/defaultstyle'

class FlatPreference(widgets.CheckPreference, widgets.CheckConditional):
    default = False
    name = 'plugin/moodbar/flat'
    condition_preference_name = 'plugin/moodbar/defaultstyle'

    def __init__(self, preferences, widget):
        widgets.CheckPreference.__init__(self, preferences, widget)
        widgets.CheckConditional.__init__(self)

class ThemePreference(widgets.CheckPreference):
    default = False
    name = 'plugin/moodbar/theme'

class ColorPreference(widgets.ColorButtonPreference, widgets.CheckConditional):
    default =  '#AAAAAA'
    name = 'plugin/moodbar/color'
    condition_preference_name = 'plugin/moodbar/theme'

    def __init__(self, preferences, widget):
        widgets.ColorButtonPreference.__init__(self, preferences, widget)
        widgets.CheckConditional.__init__(self)

