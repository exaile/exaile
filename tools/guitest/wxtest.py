"""Objects that help unit-test wxPython applications."""

import unittest

from guitest.utils import GuiTestHelperMixin, DoctestHelper
from guitest.state import guistate

import wx


#
# Stubbed GTK global functions
#

# TODO


#
# Some mutilated wxPython classes to suppress side effects
#

class wx_App(wx.App):

    def MainLoop(self):
        mainhook = guistate.main
        if mainhook is None:
            raise ValueError("mainhook not specified!")
        else:
            guistate.main = None # try to avoid infinite recursion
            guistate.level += 1
            mainhook()


class wx_Frame(wx.Frame):

    _visible = None

    def Show(self, visible):
        self._visible = visible


#
# Unit-test and doctest helpers.
#

class WxTestHelperMixin(GuiTestHelperMixin):

    toolkit_overrides = {'wx.App': wx_App,
                         'wx.Frame': wx_Frame}


# unittest helper
class WxTestCase(WxTestHelperMixin, unittest.TestCase):
    """A convenience TestCase for use in wxPython application unit tests."""

# doctest helpers
doctesthelper = DoctestHelper(WxTestHelperMixin)

setUp_param = doctesthelper.setUp_param
setUp = doctesthelper.setUp
tearDown = doctesthelper.tearDown
