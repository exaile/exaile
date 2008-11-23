"""Objects that help unit-test pyGTK applications."""

import unittest

import gtk
import gtk.glade

from guitest.utils import GuiTestHelperMixin, DoctestHelper
from guitest.state import guistate


#
# Stubbed GTK global functions
#

def pygtk_require(version):
    pass


def gtk_main():
    mainhook = guistate.main
    if mainhook is None:
        raise ValueError("mainhook not specified!")
    else:
        guistate.main = None # try to avoid infinite recursion
        guistate.level += 1
        mainhook()


def gtk_main_quit():
    guistate.level -= 1


def gtk_main_level():
    return guistate.level


def gtk_main_iteration(block=True):
    return False


#
# Some mutilated GTK classes to suppress side effects
#


class _InvisibleWidgetMixin(object):
    """A mixin that can be used to try to stop widgets from appearing onscreen.

    Its attribute `_visible` (None by default) is set to True if the widget's
    show() method or friends are called, False if hide() or friends are called.
    """

    _visible = None

    def show(self):
        self._visible = True

    def hide(self):
        self._visible = False

    show_now = show
    show_all = show
    hide_all = hide


class gtk_Window(_InvisibleWidgetMixin, gtk.Window):
    pass


class _StubbedDialogMixin(_InvisibleWidgetMixin):
    """A mixin that simulates a response to a dialog.

    Normally when a dialog's run() method is called, the application will
    block.  This mixin runs the dialog handler provided in the unit test
    code instead of waiting for input from the user.
    """

    def run(self):
        """Run the dialog and return a user-specified value.

        Invokes callable guistate.dlg_handler with the dialog instance
        as a single argument and returns the handler's return value as
        the response.
        """
        assert guistate.dlg_handler, 'dlg_handler not set'
        handler = guistate.dlg_handler
        guistate.dlg_handler = None
        response = handler(self)
        assert response is not None, 'dlg_handler returned None'
        return response


# Find and override out gtk.Dialog and all its subclasses

dialog_overrides = {}

_gtk_attrs = dir(gtk)
try:
    _gtk_attrs.remove('_gobject') # avoid a deprecation warning
except ValueError:
    pass # the attribute may be removed in the future

for attr_name in _gtk_attrs:
    try:
        attr = getattr(gtk, attr_name)
        if issubclass(attr, gtk.Dialog):
            class_name = 'gtk_' + attr_name
            stubbedclass = type(class_name, (_StubbedDialogMixin, attr), {})
            dialog_overrides['gtk.' + attr_name] = stubbedclass
    except TypeError:
        pass # most probably attr is not a class


#
# Glade overrides
#

class _ProxyMixin(object):
    """Mixin for use in proxy classes.

    This mixin is used in the glade stubs (see gtk_glade_XML).

    Note that use of this mixin breaks isinstance() for proxied widgets.
    You're better off not trying to add them to other containers by hand, etc.
    """

    _overrides = ()

    def __init__(self, obj):
        self._obj = obj

    def __getattr__(self, name):
        return getattr(self._obj, name)


def _createProxy(stubbedclass, overrides):
    """Create a proxy class that overrides methods listed in 'overrides'.

    A convenience function used in gtk_glade_XML.
    """
    cls_dict = {}
    for name in overrides:
        cls_dict[name] = getattr(stubbedclass, name).im_func
    return type(stubbedclass.__name__, (_ProxyMixin, ), cls_dict)


class gtk_glade_XML(gtk.glade.XML):
    """A stub for the gtk.glade.XML object."""

    __super_get_widget = gtk.glade.XML.get_widget

    _Dialog = gtk.Dialog
    _Window = gtk.Window
    _DialogProxy = _createProxy(dialog_overrides['gtk.Dialog'],
                                ['run', 'show', 'show_all'])
    _WindowProxy = _createProxy(gtk_Window, ['show', 'show_all'])

    def get_widget(self, name):
        widget = self.__super_get_widget(name)
        if isinstance(widget, self._Dialog):
            return self._DialogProxy(widget)
        elif isinstance(widget, self._Window):
            return self._WindowProxy(widget)
        else:
            return widget


#
# Unit-test and doctest helpers.
#

class GtkTestHelperMixin(GuiTestHelperMixin):

    toolkit_overrides = {'gtk.main': gtk_main,
                         'gtk.main_quit': gtk_main_quit,
                         'gtk.main_level': gtk_main_level,
                         'gtk.mainloop': gtk_main,
                         'gtk.mainquit': gtk_main_quit,
                         'gtk.main_iteration': gtk_main_iteration,
                         'gtk.main_iteration_do': gtk_main_iteration,
                         'gtk.Window': gtk_Window,
                         'gtk.glade.XML': gtk_glade_XML,
                         'pygtk.require': pygtk_require}
    toolkit_overrides.update(dialog_overrides)


# unittest helper
class GtkTestCase(GtkTestHelperMixin, unittest.TestCase):
    """A convenience TestCase for use in GTK application unit tests."""

# doctest helpers
doctesthelper = DoctestHelper(GtkTestHelperMixin)

setUp_param = doctesthelper.setUp_param
setUp = doctesthelper.setUp
tearDown = doctesthelper.tearDown
