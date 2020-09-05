from xl.nls import gettext


def N_(x):
    return x


class _TD:

    __slots__ = [
        'name',  # descriptive name
        'translated_name',  # translated name
        'tag_name',  # raw tag name
        'type',
        'editable',
        'min',
        'max',
        'use_disk',  # set true if should retrieve tag from disk -- which means
        # the tag cannot be stored in the database
    ]

    def __init__(self, name, type, **kwargs):
        self.name = name
        self.translated_name = gettext(name)
        self.type = type

        # these are overridable by keyword arg
        self.editable = True
        self.use_disk = False

        for k, v in kwargs.items():
            setattr(self, k, v)


#: List of metadata tags currently supported by exaile, which are
#: translated into the corresponding tag for each audio format if
#: it supports it. Prefer to extend this list's features instead
#: of creating your own list of tag metadata
#:
#: @note We use N_ (fake gettext) because for some uses these strings are
#: translated later, so we store both the translated and untranslated
#: version

tag_data = {
    # fmt: off
    'album':            _TD(N_('Album'),        'text'),
    'arranger':         _TD(N_('Arranger'),     'text'),
    'artist':           _TD(N_('Artist'),       'text'),
    'albumartist':      _TD(N_('Album artist'), 'text'),
    'author':           _TD(N_('Author'),       'text'),
    'bpm':              _TD(N_('BPM'),          'int', min=0, max=500),
    'copyright':        _TD(N_('Copyright'),    'text'),
    'comment':          _TD(N_('Comment'),      'multiline'),
    'composer':         _TD(N_('Composer'),     'text'),
    'conductor':        _TD(N_('Conductor'),    'text'),
    'cover':            _TD(N_('Cover'),        'image', use_disk=True),
    'date':             _TD(N_('Date'),         'datetime'),
    'discnumber':       _TD(N_('Disc'),         'dblnum', min=0, max=50),
    'encodedby':        _TD(N_('Encoded by'),   'text'),
    'genre':            _TD(N_('Genre'),        'text'),
    'grouping':         _TD(N_('Grouping'),     'text'),
    'isrc':             _TD(N_('ISRC'),         'text'),
    'language':         _TD(N_('Language'),     'text'),
    'lyrics':           _TD(N_('Lyrics'),       'multiline', use_disk=True),
    'lyricist':         _TD(N_('Lyricist'),     'text'),
    'organization':     _TD(N_('Organization'), 'text'),
    'originalalbum':    _TD(N_('Original album'), 'text'),
    'originalartist':   _TD(N_('Original artist'), 'text'),
    'originaldate':     _TD(N_('Original date'), 'text'),
    'part':             None,
    'performer':        _TD(N_('Performer'),    'text'),
    'title':            _TD(N_('Title'),        'text'),
    'tracknumber':      _TD(N_('Track'),        'dblnum', min=0, max=500),
    'version':          _TD(N_('Version'),      'text'),
    'website':          _TD(N_('Website'),      'text'),

    # various internal tags

    '__bitrate':        _TD(N_('Bitrate'),      'bitrate', editable=False),
    '__basedir':        None,
    '__date_added':     _TD(N_('Date added'),   'timestamp', editable=False),
    '__last_played':    _TD(N_('Last played'),  'timestamp', editable=False),
    '__length':         _TD(N_('Length'),       'time', editable=False),
    '__loc':            _TD(N_('Location'),     'location', editable=False),
    '__modified':       _TD(N_('Modified'),     'timestamp', editable=False),
    '__playtime':       _TD(N_('Play time'),    'time', editable=False),
    '__playcount':      _TD(N_('Times played'), 'int', editable=False),
    '__rating':         None,  # currently special.
    '__startoffset':    _TD(N_('Start offset'), 'time', min=0, max=3600),  # TODO: calculate these parameters
    '__stopoffset':     _TD(N_('Stop offset'),  'time', min=0, max=3600),
    # fmt: on
}

disk_tags = set()

for k, v in tag_data.items():
    if v:
        v.tag_name = k
        if v.use_disk:
            disk_tags.add(k)


def get_default_tagdata(tag):
    """If the tagname is not in tag_data, you can use this function
    to get a _TD object for it"""

    return _TD(tag, 'text', editable=(not tag.startswith('__')), tag_name=tag)
