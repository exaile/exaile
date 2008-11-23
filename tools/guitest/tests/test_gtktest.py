"""Tests for the fake_gtk module."""

import unittest
import doctest
import sys
import os

from guitest.gtktest import GtkTestCase, GtkTestHelperMixin
from guitest.gtktest import guistate, setUp, tearDown

import pygtk
import gtk
import gtk.glade


def test_Window():
    """Tests for the overridden Window class.

    show() and hide() should set `_visible`.

        >>> w = gtk.Window()
        >>> print w._visible
        None
        >>> w.show()
        >>> w._visible
        True

    The window has not been really shown:

        >>> w.get_property('visible')
        False

    hide() is also handled:

        >>> w.hide()
        >>> w._visible
        False

    Associated methods: show_now(), show_all(), hide_all()

        >>> w.show_now()
        >>> w._visible
        True
        >>> w.get_property('visible')
        False

        >>> w.hide_all()
        >>> w._visible
        False

        >>> w.show_all()
        >>> w._visible
        True
        >>> w.get_property('visible')
        False

    """

def test_Dialog():
    """Tests for the overridden Dialog class.

    Dialogs, like Windows, should never be really shown:

        >>> dlg = gtk.Dialog()
        >>> dlg.show()
        >>> dlg._visible # fake
        True
        >>> dlg.get_property('visible') # real
        False

    First, if we invoke Dialog.run() without any other settings, we get an
    assertion error:

        >>> dlg = gtk.Dialog()
        >>> dlg.run()
        Traceback (most recent call last):
            ...
        AssertionError: dlg_handler not set

    We have to set guistate.dlg_handler:

        >>> def sample_handler(dialog):
        ...     if dialog is dlg:
        ...         print 'Parameter correct'
        ...     return 'cancel'
        >>> guistate.dlg_handler = sample_handler

        >>> response = dlg.run()
        Parameter correct
        >>> response
        'cancel'

    You can deal with consecutive dialogs by assigning the next handler to
    dlg_handler inside the running one.

        >>> def handler1(dialog):
        ...     guistate.dlg_handler = handler2
        ...     return 1
        >>> def handler2(dialog):
        ...     return 2
        >>> guistate.dlg_handler = handler1

        >>> dlg.run()
        1
        >>> dlg.run()
        2

    Subclasses of Dialog are also dealt with (see also test_DialogSubclasses).

        >>> fs = gtk.FontSelectionDialog("dummy")
        >>> guistate.dlg_handler = lambda dialog: 'boo'
        >>> fs.run()
        'boo'

    glade has to substitute dialogs from XML with proxies whose run()
    method behaves similarly.

        >>> path = os.path.dirname(__file__)
        >>> f = open(os.path.join(path, 'sample.glade'))
        >>> tree = gtk.glade.XML(os.path.join(path, 'sample.glade'))

        >>> dlg = tree.get_widget('dialog')
        >>> dlg.get_title()
        'Sample dialog'
        >>> guistate.dlg_handler = lambda dialog: 'glade'
        >>> dlg.run()
        'glade'

    Subclasses of Dialog are also handled:

        >>> fontsel = tree.get_widget('fontsel')
        >>> fontsel.get_font_name()
        '...'
        >>> guistate.dlg_handler = lambda dialog: 'glade2'
        >>> fontsel.run()
        'glade2'

    """

def test_DialogSubclasses():
    """Tests for subclasses of Dialog.

    There are subclasses of Dialog in GTK which should also be modified
    in the same way as the main Dialog class.

    We will try to make an exhaustive test that finds and checks all subclasses
    of gtk.Dialog.  For that reason we will need to peek into the innards of
    gtktest to get the real gtk.Dialog class.

        >>> from guitest.gtktest import doctesthelper
        >>> real_Dialog = None
        >>> for module, name, cls in doctesthelper.doctestmgr._original:
        ...     if module is gtk and name == 'Dialog':
        ...         real_Dialog = cls
        ...         break

    We have found the original gtk.Dialog:

        >>> real_Dialog
        <type 'gtk.Dialog'>

    Now we check that each subclass of the real gtk.Dialog is also a subclass
    of _StubbedDialogMixin, which provides the stub for the run() method.

        >>> from guitest.gtktest import _StubbedDialogMixin
        >>> _gtk_attrs = dir(gtk)
        >>> try:
        ...     _gtk_attrs.remove('_gobject') # avoid a deprecation warning
        ... except ValueError:
        ...     pass # the attribute may be removed in the future
        >>> for attr_name in _gtk_attrs:
        ...     try:
        ...         attr = getattr(gtk, attr_name)
        ...         if issubclass(attr, real_Dialog):
        ...             assert issubclass(attr, _StubbedDialogMixin), attr_name
        ...             assert attr.__name__ == 'gtk_' + attr_name
        ...     except TypeError:
        ...         pass # most probably attr is not a class

    """


def test_gtk_functions():
    """Test for global gtk functions.

    pygtk_require does nothing at the moment.  It prevents the real pygtk
    from complaining that gtk has been imported already.

        >>> pygtk.require('2.00')

    The functions dealing with the main loop are important yet very simple.

        >>> gtk.main_level()
        0

        >>> def fake_main():
        ...     print 'Running main, level:', gtk.main_level()
        >>> guistate.main = fake_main
        >>> gtk.main()
        Running main, level: 1

    main_iteration simply returns False:

        >>> gtk.main_iteration()
        False
        >>> gtk.main_iteration(block=False)
        False
        >>> gtk.main_iteration_do()
        False
        >>> gtk.main_iteration_do(block=False)
        False

    Currently we do not automatically decrement main_level when a call
    to main() returns, as we expect an explicit call to main_quit() in the body
    of main().

        >>> gtk.main_level()
        1

        >>> gtk.main_quit()
        >>> gtk.main_level()
        0

    """


def test_GtkTestHelperMixin():
    """Tests for GtkTestHelperMixin.

        >>> from guitest.utils import GuiTestHelperMixin
        >>> issubclass(GtkTestHelperMixin, GuiTestHelperMixin)
        True
        >>> GtkTestHelperMixin.toolkit_overrides
        {...}

    """


def test_GtkTestCase():
    """Tests for GtkTestCase.

        >>> issubclass(GtkTestCase, GtkTestHelperMixin)
        True
        >>> issubclass(GtkTestCase, unittest.TestCase)
        True

    """


def test_doctest_support():
    """Tests for doctest support.

        >>> from guitest.gtktest import setUp, setUp_param, tearDown

    We only have a quick glance at the functions because they are already
    being used in this docsuite (see test_suite()) and everything would break
    if they did not work.

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
