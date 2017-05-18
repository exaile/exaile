'''
    Provided so that we can build docs without needing to have any
    dependencies installed (such as for RTFD).

    Derived from http://read-the-docs.readthedocs.org/en/latest/faq.html
'''

import sys


class Mock(object):

    __all__ = []

    def __init__(self, *args, **kwargs):
        pass

    def __call__(self, *args, **kwargs):
        return Mock()

    @classmethod
    def __getattr__(cls, name):
        if name in ('__file__', '__path__'):
            return '/dev/null'
        else:
            return Mock()

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

MOCK_MODULES = [
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

for mod_name in MOCK_MODULES:
    sys.modules[mod_name] = Mock()


# player hack
import xl.settings

orig_get_option = xl.settings.get_option


def option_hack(name, default):
    if name == 'player/engine':
        return 'rtfd_hack'
    else:
        return orig_get_option(name, default)

xl.settings.get_option = option_hack
