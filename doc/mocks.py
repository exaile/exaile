'''
    Provided so that we can build docs without needing to have any
    dependencies installed (such as for RTFD).

    Derived from https://read-the-docs.readthedocs.org/en/latest/faq.html
'''

import sys


class MockGiModule:
    def __init__(self, *args, **kwargs):
        pass

    def __call__(self, *args, **kwargs):
        return MockGiModule()

    @classmethod
    def __getattr__(cls, name):
        if name in ('__file__', '__path__'):
            return '/dev/null'
        elif name in '__mro_entries__':
            raise AttributeError("'MockGiModule' object has no attribute '%s'" % (name))
        elif name in 'GObject':
            # This corresponds to GObject class in the GI (GObject)
            # module - we need to return type instead of an instance!
            #
            # Note: we need to do this for each class that comes from
            # a GI module AND is involved in multiple-inheritance in our
            # codebase in order to avoid "TypeError: metaclass conflict"
            # errors.
            return MockGiModule
        else:
            return MockGiModule()

    # glib mocks
    @classmethod
    def get_user_data_dir(cls):
        return '/tmp'

    @classmethod
    def get_user_config_dir(cls):
        return '/tmp'

    @classmethod
    def get_user_cache_dir(cls):
        return '/tmp'

    # gtk/gdk mocks
    class ModifierType:
        SHIFT_MASK = 0

    @classmethod
    def accelerator_parse(cls, *args):
        return [0, 0]

class Mock:
    __all__ = []

    def __init__(self, *args, **kwargs):
        pass

    def __call__(self, *args, **kwargs):
        return Mock()

    @classmethod
    def __getattr__(cls, name):
        if name in ('__file__', '__path__'):
            return '/dev/null'
        elif name in ('__qualname__',):
            return ""
        elif name in ('__mro_entries__',):
            raise AttributeError("'Mock' object has no attribute '%s'" % (name))
        elif name in ('Gio', 'GLib', 'GObject', 'Gst', 'Gtk', 'Gdk'):
            # These are reached via 'from gi.repository import x' and
            # correspond to GI sub-modules - need to return an instance
            # of our mock GI module
            return MockGiModule()
        else:
            return Mock()

MOCK_MODULES = [
    'bsddb3',
    'cairo',

    'dbus',
    'dbus.service',

    'gi',
    'gi.repository',
    'gi.repository.Gio',
    'gi.repository.GLib',
    'gi.repository.GObject',
    'gi.repository.Gst',
    'gi.repository.Gtk',

    'mutagen',
    'mutagen.apev2',
    'mutagen.ogg',
    'mutagen.flac',
]


def import_fake_modules():
    for mod_name in MOCK_MODULES:
        sys.modules[mod_name] = Mock()


def fake_xl_settings():
    # player hack
    import xl.settings

    def option_hack(name, default):
        if name == 'player/engine':
            return 'rtfd_hack'
        else:
            return orig_get_option(name, default)

    orig_get_option = xl.settings.get_option
    xl.settings.get_option = option_hack
