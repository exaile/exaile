"""Tests for the guitest.utils module."""

import unittest
import doctest
import sys

from guitest.utils import GuiTestHelperMixin, DoctestHelper
from guitest.state import guistate, GuiState


def doctest_GuiState():
    """Tests for GuiState.

    GuiState is a simple object that stores information about a test fixture.

        >>> state = GuiState()

        >>> print state.main
        None
        >>> print state.level
        0
        >>> print state.dlg_handler
        None
        >>> print state.calls
        []

    GuiState has some simple methods:

        >>> def fake_main(): print 'fake main'
        >>> state.set_main(fake_main)
        >>> state.main()
        fake main

        >>> def fake_dlg_handler(): print 'fake dlg_handler'
        >>> state.set_dlg_handler(fake_dlg_handler)
        >>> state.dlg_handler()
        fake dlg_handler

    """


def doctest_GuiTestHelperMixin():
    """Tests for GuiTestHelperMixin.

    First, let's make sure that setUp & tearDown does not fail with no options
    specified:

        >>> helper = GuiTestHelperMixin()
        >>> helper.setUp()

        >>> helper._original
        []
        >>> helper.tearDown()

    In the next step we will need a module (which we simulate by using a
    class):

        >>> class ModuleStub(object):
        ...     obj = "original"
        ...     class Logged(object):
        ...         def noop(self, arg): pass
        >>> module = sys.modules['_override_test'] = ModuleStub

    Let's try overriding the obj attribute.  We use a string to make it easier
    to test, but in reality this will usually be a function or a class.  At
    the same time we test that 'overrides' takes precedence over
    'toolkit_overrides'.

        >>> helper = GuiTestHelperMixin()
        >>> helper.toolkit_overrides = {'_override_test.obj': "overridden"}
        >>> helper.overrides = {'_override_test.obj': "custom overridden"}
        >>> helper.logging = {'_override_test.Logged': ['noop']}
        >>> helper.setUp()

    The attribute has been overridden:

        >>> module.obj
        'custom overridden'

    Logging works:

        >>> module.Logged().noop('foo')
        >>> guistate.calls
        [(<...Logged object...>, 'noop', ('foo',), {})]

    The original objects have been stored in the attribute _original.

        >>> len(helper._original)
        3
        >>> helper._original[0] # from toolkit_overrides
        (<...ModuleStub...>, 'obj', 'original')
        >>> helper._original[1] # from overrides
        (<class '__main__.ModuleStub'>, 'obj', 'overridden')
        >>> helper._original[2]
        (<...Logged...>, 'noop', <unbound method Logged.noop>)

    tearDown should put things back into their places:

        >>> helper.tearDown()

        >>> module.obj
        'original'
        >>> hasattr(helper, '_original')
        False

        >>> guistate.calls = []
        >>> module.Logged().noop('foo')
        >>> guistate.calls
        []

    Let's clean up:

        >>> del sys.modules['_override_test']

    """

def doctest_GuiTestHelperMixin_override():
    """Tests for overriding in GuiTestHelperMixin.

    A more thorough test for _override(): we will use a module hierarchy
    (simulated by nested classes):

        >>> class ModuleStub(object):
        ...     class sub(object):
        ...         class subsub(object):
        ...             obj = 'original'
        >>> module = sys.modules['_override_test'] = ModuleStub

        >>> helper = GuiTestHelperMixin()
        >>> helper._original = []
        >>> helper._override('_override_test.sub.subsub.obj', 'overridden')
        >>> module.sub.subsub.obj
        'overridden'

    _override() will create an object if it's not there:

        >>> helper._override('_override_test.sub.subsub.another', 'new')
        >>> module.sub.subsub.another
        'new'

    tearDown should restore 'obj' and delete 'another':

        >>> helper.tearDown()
        >>> module.sub.subsub.obj
        'original'
        >>> module.sub.subsub.another
        Traceback (most recent call last):
            ...
        AttributeError: type object 'subsub' has no attribute 'another'

    Final test: _override should be able to handle static classes, i.e.,
    classes whose attributes can not be set.  This applies to most GTK widgets,
    because they come from a C extension.  We then create a class that inherits
    from them and add our methods there.

        >>> helper = GuiTestHelperMixin()
        >>> helper._original = []

        >>> def fake_show(self): print "showing"
        >>> helper._override('gtk.Entry.show', fake_show)

        >>> helper._override('gtk.Entry.new_attr', 'new')

        >>> import gtk
        >>> e = gtk.Entry()
        >>> e.show()
        showing
        >>> e.new_attr
        'new'

    tearDown works properly here too:

        >>> helper._original
        [(<module 'gtk' from '...'>, 'Entry', <type 'gtk.Entry'>), \
(<class 'guitest.utils.Entry'>, 'new_attr', None)]

        >>> helper.tearDown()
        >>> e = gtk.Entry()
        >>> e.show()
        >>> e.new_attr
        Traceback (most recent call last):
            ...
        AttributeError: 'gtk.Entry' object has no attribute 'new_attr'

    """


def doctest_GuiTestHelperMixin_logging():
    """Tests for automatic logging support in GuiTestHelperMixin.

        >>> helper = GuiTestHelperMixin()
        >>> class ModuleStub(object):
        ...     class SomeObj(object):
        ...         def hello(self, name, dot=True):
        ...             print 'hello,', name + (dot and '.' or '')
        >>> module = sys.modules['_override_test'] = ModuleStub
        >>> helper._original = []
        >>> helper._logCalls('_override_test.SomeObj')

        >>> o = module.SomeObj()
        >>> o.hello('gintas')
        hello, gintas.
        >>> o.hello('ignas', dot=False)
        hello, ignas

        >>> len(guistate.calls)
        2
        >>> guistate.calls[0][1:]
        ('hello', ('gintas',), {})
        >>> guistate.calls[0][0] is o
        True
        >>> guistate.calls[1][1:]
        ('hello', ('ignas',), {'dot': False})
        >>> guistate.calls[1][0] is o
        True

    Let's clear the fixture for the next experiment:

        >>> helper.tearDown()

    We will now try attaching a logger to a C extension class:

        >>> helper = GuiTestHelperMixin()
        >>> helper._original = []
        >>> helper._logCalls('gtk.Entry', ['hide'])

        >>> import gtk
        >>> entry = gtk.Entry()
        >>> entry.hide()
        >>> guistate.calls
        [(<Entry object ...>, 'hide', (), {})]

    Clean up:

        >>> del sys.modules['_override_test']
        >>> helper.tearDown()

    """


def doctest_GuiTestHelperMixin_resolvePath():
    """Tests for GuiTestHelperMixin._resolvePath.

        >>> helper = GuiTestHelperMixin()
        >>> def resolvePath(path):
        ...     path = path.split('.')
        ...     for obj in helper._resolvePath(path):
        ...         print repr(obj)

        >>> resolvePath('guitest')
        <module 'guitest' ...>

        >>> resolvePath('guitest.gtktest')
        <module 'guitest' ...>
        <module 'guitest.gtktest' ...>

        >>> resolvePath('guitest.tests.test_utils.test_suite')
        <module 'guitest' ...>
        <module 'guitest.tests' ...>
        <module 'guitest.tests.test_utils' ...>
        <function test_suite at ...>

        >>> resolvePath('guitest.nonexistent')
        Traceback (most recent call last):
            ...
        ImportError: No module named nonexistent

    """


def doctest_DoctestHelper():
    """Tests for DoctestHelper.

    We will need a fake helper tha will be wrapped:

        >>> class FakeHelper(object):
        ...     def setUp(self):
        ...         print "Setting up"
        ...     def tearDown(self):
        ...         print "Tearing down"

    >>> helper = DoctestHelper(FakeHelper)

    First, no overrides:

        >>> helper.setUp()
        Setting up

        >>> helper.doctestmgr.overrides
        {}

        >>> helper.tearDown()
        Tearing down

        >>> print helper.doctestmgr
        None

    Let's add a few overrides and logging.  We will have to use the
    more complex form.

        >>> overrides = {'gtk.Entry.something': 'new'}
        >>> logging = {'gtk.Entry': ['show', 'hide']}
        >>> setup = helper.setUp_param(overrides=overrides, logging=logging)
        >>> setup()
        Setting up

        >>> helper.doctestmgr.overrides
        {'gtk.Entry.something': 'new'}
        >>> helper.doctestmgr.logging
        {'gtk.Entry': ['show', 'hide']}

        >>> helper.tearDown()
        Tearing down

        >>> print helper.doctestmgr
        None

    """


def test_suite():
    suite = doctest.DocTestSuite(optionflags=doctest.ELLIPSIS)
    return unittest.TestSuite([suite])


if __name__ == '__main__':
    unittest.main(defaultTest='test_suite')
