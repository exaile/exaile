# Copyright (C) 2012 Mathias Brodala
#
# This program is free software; you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation; either version 2, or (at your option)
# any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program; if not, write to the Free Software
# Foundation, Inc., 675 Mass Ave, Cambridge, MA 02139, USA.

from gtk.gdk import color_parse

from xl import settings

from alphacolor import alphacolor_parse

# Mapping from old to new setting names
# Note that bg_color and opacity are not 
# migrated to allow for a new look and feel
__settings_map = {
    'h': ('height', lambda value: max(value, 110)),
    'w': 'width',
    'duration': ('display_duration', lambda value: int(value / 1000)),
    'show_progress': 'show_progress'
}
# List of tags officially supported in the old OSD
__tags_list = [
    'title',
    'artist',
    'album',
    '__length',
    'tracknumber',
    '__bitrate',
    'genre',
    'year',
    '__rating'
]

def migrate_settings():
    """
        Migrates the old "osd" settings to "plugin/osd"
    """
    if not settings.MANAGER.has_section('osd') or \
       settings.MANAGER.has_section('plugin/osd'):
        return

    for oldname, newname in __settings_map.iteritems():
        value = settings.get_option('osd/%s' % oldname)

        if value is not None:
            if isinstance(newname, tuple):
                value = newname[1](value)
                newname = newname[0]
            settings.set_option('plugin/osd/%s' % newname, value)

    # Special handling for position
    position = [
        settings.get_option('osd/x', 20),
        settings.get_option('osd/y', 20)
    ]
    settings.set_option('plugin/osd/position', position)

    # Special handling for format
    display_text = settings.get_option('osd/display_text')
    if display_text is not None:
        format = display_text

        # Be sure to not replace more than necessary
        for tag in __tags_list:
            format = format.replace('{%s}' % tag, '$%s' % tag)

        attributes = []

        text_font = settings.get_option('osd/text_font')

        if text_font is not None:
            attributes += ['font_desc="%s"' % text_font]

        text_color = settings.get_option('osd/text_color')

        if text_color is not None:
            color = color_parse(text_color)
            attributes += ['foreground="%s"' % str(color)]

        if attributes:
            format = '<span %s>%s</span>' % (' '.join(attributes), format)

        settings.set_option('plugin/osd/format', format)

