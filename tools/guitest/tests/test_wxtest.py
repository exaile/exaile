"""Tests for the fake_gtk module."""

import unittest
import doctest
import os

try:
    import wx
except ImportError:
    import sys
    print >> sys.stderr, 'wxPython is not available, skipping related tests.'

    def test_suite():
        return unittest.TestSuite() # return an empty test suite

else: # wxPython is available
    from guitest.wxtest import WxTestCase, WxTestHelperMixin
    from guitest.wxtest import guistate, setUp, tearDown

    def test_suite():
        return doctest.DocTestSuite(setUp=setUp, tearDown=tearDown,
                                    optionflags=doctest.ELLIPSIS)


def test_App():
    """Tests for the overridden Dialog class.


    """


def test_Frame():
    """Tests for the overridden Window class.

    show() and hide() should set `_visible`.

        >>> app = wx.App()
        >>> w = wx.Frame(None)
        >>> print w._visible
        None
        >>> w.Show(True)
        >>> w._visible
        True

    The window has not been really shown:

        >>> w.IsShown()
        False

    Hiding works as expected too:

        >>> w.Show(False)
        >>> w.IsShown()
        False

    """


def test_WxTestHelperMixin():
    """Tests for WxTestHelperMixin.

        >>> from guitest.utils import GuiTestHelperMixin
        >>> issubclass(WxTestHelperMixin, GuiTestHelperMixin)
        True
        >>> WxTestHelperMixin.toolkit_overrides
        {...}

    """


def test_WxTestCase():
    """Tests for WxTestCase.

        >>> issubclass(WxTestCase, WxTestHelperMixin)
        True
        >>> issubclass(WxTestCase, unittest.TestCase)
        True

    """


def test_doctest_support():
    """Tests for doctest support.

        >>> from guitest.wxtest import setUp, setUp_param, tearDown

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


if __name__ == '__main__':
    unittest.main(defaultTest='test_suite')
