"""Objects that help unit-test Tkinter applications."""

import unittest
from guitest.utils import GuiTestHelperMixin, DoctestHelper
from guitest.state import guistate


def Tkinter_mainloop():
    mainhook = guistate.main
    if mainhook is None:
        raise ValueError("mainhook not specified!")
    else:
        guistate.main = None # try to avoid infinite recursion
        guistate.level += 1
        mainhook()


#
# Unit-test and doctest helpers.
#

class TkinterTestHelperMixin(GuiTestHelperMixin):

    toolkit_overrides = {'Tkinter.mainloop': Tkinter_mainloop}


class TkinterTestCase(TkinterTestHelperMixin, unittest.TestCase):
    """A convenience TestCase for use in Tkinter application unit tests."""

# doctest helper
doctesthelper = DoctestHelper(TkinterTestHelperMixin)

setUp_param = doctesthelper.setUp_param
setUp = doctesthelper.setUp
tearDown = doctesthelper.tearDown
