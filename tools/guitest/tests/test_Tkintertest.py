"""Tests for the fake_Tkinter module."""

import unittest
import doctest

from guitest.Tkintertest import TkinterTestHelperMixin, TkinterTestCase
from guitest.Tkintertest import guistate, setUp, tearDown

import Tkinter


def test_mainloop():
    """Test for global Tkinter functions.

    The functions dealing with the main loop are important yet very simple.

        >>> def fake_main():
        ...     print 'Running main, level:', guistate.level
        >>> guistate.main = fake_main
        >>> Tkinter.mainloop()
        Running main, level: 1

        >>> guistate.level
        1

    """


def test_TkinterTestHelperMixin():
    """Tests for TkinterTestHelperMixin.

        >>> from guitest.utils import GuiTestHelperMixin
        >>> issubclass(TkinterTestHelperMixin, GuiTestHelperMixin)
        True
        >>> TkinterTestHelperMixin.toolkit_overrides
        {...}

    """


def test_TkinterTestCase():
    """Tests for TkinterTestCase.

        >>> issubclass(TkinterTestCase, TkinterTestHelperMixin)
        True
        >>> issubclass(TkinterTestCase, unittest.TestCase)
        True

    """


def test_doctest_support():
    """Tests for doctest support.

        >>> from guitest.Tkintertest import setUp, setUp_param, tearDown

    We only have a quick glance at the functions because they are already
    being used in this docsuite and everything would break if they did not
    work.

        >>> setUp
        <bound method DoctestHelper.setUp of \
<guitest.utils.DoctestHelper object at ...>>

        >>> setUp_param
        <bound method DoctestHelper.setUp_param of \
<guitest.utils.DoctestHelper object at ...>>

        >>> tearDown
        <bound method DoctestHelper.tearDown of \
<guitest.utils.DoctestHelper object at ...>>

    """


def test_suite():
    return doctest.DocTestSuite(setUp=setUp, tearDown=tearDown,
                                optionflags=doctest.ELLIPSIS)


if __name__ == '__main__':
    unittest.main(defaultTest='test_suite')
