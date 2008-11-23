"""Utilities for testing GUI applications."""

from guitest.state import guistate

#
# Unit test support mixin.
#

class GuiTestHelperMixin(object):
    """A class for use in setting up or tearing down GTK test fixtures.

    This class does not inherit from unittest.TestCase because it is used
    both in unittest and doctest setup.
    """

    # to be overridden in subclasses
    toolkit_overrides = {}
    overrides = {}
    logging = {}

    def setUp(self):
        guistate.reset()
        self._original = []
        for name, obj in self.toolkit_overrides.items():
            self._override(name, obj)
        for name, obj in self.overrides.items():
            self._override(name, obj)
        for name, obj in self.logging.items():
            self._logCalls(name, obj)

    def _resolvePath(self, path):
        """Transform a sequence of identifiers to a sequence of objects.

        'path' is a sequence of strings, that, when connected with dots,
        would form a python dot-path.  The function returns a sequence
        of objects of the same length.  An exception is raised if the
        path is invalid.
        """
        obj = __import__(path[0])
        objs = [obj]
        fullpath = path[0]
        for name in path[1:]:
            fullpath += '.' + name
            if not hasattr(obj, name):
                __import__(fullpath) # not very clean, but seems to work
            obj = getattr(obj, name)
            objs.append(obj)
        return objs

    def _override(self, name, obj):
        """Override object identified by a dot-separated path with 'obj'.

        This method relies on the fact that all modules have their submodules
        as attribute, e.g., if I have the module 'gtk', I can always find
        'gtk.glade' by getattr(gtk, 'glade').

        TODO: this could be usable on any modules, not just ones from our
        fake GTK, so it would be a good idea to lift this restriction.
        """
        path = name.split('.')
        assert len(path) > 1, 'module name not provided'
        obj_name = path[-1]

        objs = self._resolvePath(path[:-1])
        container = objs[-1]
        try:
            original_class = getattr(container, obj_name, None)
            setattr(container, obj_name, obj)
            self._original.append((container, obj_name, original_class))
        except TypeError:
            # We have a static class; we will have to modify its container.
            # This works for global functions in gtk too because their
            # container is an ordinary python module (fake_gtk).
            name = container.__name__
            prev_container = objs[-2]
            subclass = type(name, (container, ), {obj_name: obj})
            setattr(prev_container, name, subclass)
            self._original.append((prev_container, name, container))

    def _logCalls(self, dot_path, methods=None):
        """Add a logger to methods in class identified by dot_path.

        The list of methods can be supplied as the 'methods' argument.  If it
        is not provided, all methods are registered for logging.
        """
        path = dot_path.split('.')
        assert len(path) > 1, 'module name not provided'

        cls = self._resolvePath(path)[-1]
        if not methods:
            # Iterate through all methods except the special ones which
            # cause trouble...
            methods = [name for name in dir(cls)
                       if (not name.startswith('__')
                           and callable(getattr(cls, name)))]
        for name in methods:
            orig_method = getattr(cls, name)
            def new_method(self, *args, **kwargs):
                guistate.calls.append((self, name, args, kwargs))
                return orig_method(self, *args, **kwargs)
            self._override(dot_path + '.' + name, new_method)

    def tearDown(self):
        guistate.reset()
        self._original.reverse()
        for parent, name, obj in self._original:
            if obj is not None:
                setattr(parent, name, obj)
            else:
                delattr(parent, name)
        del self._original


#
# Doctest support functions
#

class DoctestHelper(object):
    """A helper class for GUI application doctests.

    Instances of this class wrap subclasses of GuiTestHelperMixin.  You will
    normally want to instantiate this class once and export its methods.
    """

    def __init__(self, doctestmgr_factory):
        self.doctestmgr_factory = doctestmgr_factory
        self.doctestmgr = None

    def setUp_param(self, overrides={}, logging={}):
        """Parametrized setUp for doctests."""
        def setup(test=None):
            self.doctestmgr = self.doctestmgr_factory()
            self.doctestmgr.overrides = overrides
            self.doctestmgr.logging = logging
            self.doctestmgr.setUp()
        return setup # we were called to get a setUp function

    def setUp(self, test=None):
        """Plain setUp as a convenience function for doctests."""
        setUp = self.setUp_param()
        setUp(test)

    def tearDown(self, test=None):
        """tearDown for doctests."""
        assert self.doctestmgr is not None, "doctest setup not invoked!"
        self.doctestmgr.tearDown()
        self.doctestmgr = None


#
# Miscellaneous
#

def mainloop_handler(app_main):
    """A helper for unit-test methods running instead of the main loop.

    This function takes as an argument the function which invokes gtk.main().
    A decorator for TestCase methods is returned.  In Python 2.4 you can
    use this helper like this:

        @mainloop_helper(my_app.main)
        def test_myApp(self):
            ...

    If you need to preserve compatibility with Python 2.3, you will not
    be able to use the decorator syntax:

        def test_myApp(self):
            ...
        test_myApp = mainloop_helper(my_app.main)(test_myApp)

    """
    # XXX No unit tests.
    def decorator(method):
        def proxy(self):
            """Run the application and then the test."""
            global guistate
            guistate.main = lambda: method(self)
            app_main()
        return proxy
    return decorator
