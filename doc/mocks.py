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
        elif name[0] == name[0].upper():
            mockType = type(name, (), {})
            mockType.__module__ = __name__
            return mockType
        else:
            return Mock()
    
    # glib mocks
    
    def get_user_data_dir(self):
        return '/tmp'
    
    def get_user_config_dir(self):
        return '/tmp'
    
    def get_user_cache_dir(self):
        return '/tmp'

MOCK_MODULES = [
    'cairo',
    'dbus',
    'gio',
    'glib',
    'gst',
    'gtk',
    'gobject',
    'pygst',
    'pygtk',
    
    'mutagen',
    'mutagen.apev2',
    'mutagen.ogg',
    'mutagen.flac',
]

for mod_name in MOCK_MODULES:
    sys.modules[mod_name] = Mock()