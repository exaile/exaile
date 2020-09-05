# Copyright (C) 2008-2010 Adam Olsen
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
# Foundation, Inc., 51 Franklin Street, Fifth Floor, Boston, MA  02110-1301, USA.
#
#
# The developers of the Exaile media player hereby grant permission
# for non-GPL compatible GStreamer and Exaile plugins to be used and
# distributed together with GStreamer and Exaile. This permission is
# above and beyond the permissions granted by the GPL license by which
# Exaile is covered. If you modify this code, you may extend this
# exception to your version of the code, but you are not obligated to
# do so. If you do not wish to do so, delete this exception statement
# from your version.

from gi.repository import Gtk

from xl import main, playlist, settings

from xl.nls import gettext as _

from . import dialogs
from .filter import (
    EntryField,
    FilterDialog,
    ComboEntryField,
    MultiEntryField,
    NullField,
    QuotedEntryField,
    SpinButtonAndComboField,
    SpinLabelField,
)

import logging

logger = logging.getLogger(__name__)


def N_(x):
    return x


class EntrySecondsField(MultiEntryField):
    def __init__(self):
        MultiEntryField.__init__(self, (50, _('seconds')))


class EntryAndEntryField(MultiEntryField):
    def __init__(self):
        # TRANSLATORS: Logical AND used for smart playlists
        MultiEntryField.__init__(self, (50, _('and'), 50))


class EntryDaysField(MultiEntryField):
    def __init__(self):
        MultiEntryField.__init__(self, (50, _('days')))


class PlaylistField(ComboEntryField):
    def __init__(self):
        playlists = []
        playlists.extend(main.exaile().smart_playlists.list_playlists())
        playlists.extend(main.exaile().playlists.list_playlists())
        playlists.sort()
        ComboEntryField.__init__(self, playlists)


DATE_FIELDS = [N_('seconds'), N_('minutes'), N_('hours'), N_('days'), N_('weeks')]


class SpinDateField(SpinButtonAndComboField):
    def __init__(self):
        SpinButtonAndComboField.__init__(self, DATE_FIELDS)


class SpinSecondsField(SpinLabelField):
    def __init__(self):
        SpinLabelField.__init__(self, _('seconds'))


class SpinRating(SpinLabelField):
    def __init__(self):
        SpinLabelField.__init__(self, '', settings.get_option("rating/maximum", 5), 0)


class SpinNothing(SpinLabelField):
    def __init__(self):
        SpinLabelField.__init__(self, '')


# This sets up the CRITERIA for all the available types of tags
# that exaile supports. The actual CRITERIA dict is populated
# using xl.metadata.tags.tag_data.
#
# NOTE: The following strings are already marked for translation in _TRANS and
# _NMAP, and will be really translated by filtergui; no need to clutter the
# code here.
_criteria_types = {
    # fmt: off

    # TODO
    'bitrate': [
        ('is', SpinNothing),
        ('less than', SpinNothing),
        ('greater than', SpinNothing),
        ('between', EntryAndEntryField),
        ('at least', SpinNothing),
        ('at most', SpinNothing),
        ('is set', NullField),
        ('is not set', NullField),
    ],

    'image': None,

    'int': [
        ('is', SpinNothing),
        ('less than', SpinNothing),
        ('greater than', SpinNothing),
        ('between', EntryAndEntryField),
        ('at least', SpinNothing),
        ('at most', SpinNothing),
        ('is set', NullField),
        ('is not set', NullField),
    ],

    'location': [
        ('is', QuotedEntryField),
        ('is not', QuotedEntryField),
        ('contains', QuotedEntryField),
        ('does not contain', QuotedEntryField),
        ('regex', QuotedEntryField),
        ('not regex', QuotedEntryField),
    ],

    'text': [
        ('is', EntryField),
        ('is not', EntryField),
        ('contains', EntryField),
        ('does not contain', EntryField),
        ('contains word', EntryField),
        ('does not contain word', EntryField),
        ('regex', EntryField),
        ('not regex', EntryField),
        ('is set', NullField),
        ('is not set', NullField),
    ],

    'time': [
        ('at least', SpinSecondsField),
        ('at most', SpinSecondsField),
        ('is', SpinSecondsField),
        ('is not', SpinSecondsField),
    ],

    'timestamp': [
        ('in the last', SpinDateField),
        ('not in the last', SpinDateField),
    ],

    '__playlist': [
        ('Track is in', PlaylistField),
        ('Track not in', PlaylistField),
    ],

    '__rating': [
        ('greater than', SpinRating),
        ('less than', SpinRating),
        ('at least', SpinRating),
        ('at most', SpinRating),
    ],
    # fmt: on
}

# aliases
_criteria_types['datetime'] = _criteria_types['text']  # TODO: fix
_criteria_types['multiline'] = _criteria_types['text']
_criteria_types['dblnum'] = _criteria_types['int']


# This gets populated below. Only add special tags/searches that don't have a
# valid entry in tag_data
CRITERIA = [
    ('Rating', _criteria_types['__rating']),
    ('Playlist', _criteria_types['__playlist']),
]

# NOTE: We use N_ (fake gettext) because these strings are translated later by
# the filter GUI. If we use _ (real gettext) here, filtergui will try to
# translate already-translated strings, which makes no sense. This is partly due
# to the old design of storing untranslated strings (instead of operators) in
# the dynamic playlist database.

_TRANS = {
    # TRANSLATORS: True if haystack is equal to needle
    N_('is'): '==',
    # TRANSLATORS: True if haystack is not equal to needle
    N_('is not'): '!==',
    # TRANSLATORS: True if the specified tag is present (uses the NullField
    # to compare to __null__)
    N_('is set'): '<!==>',
    # TRANSLATORS: True if the specified tag is not present (uses the NullField
    # to compare to __null__)
    N_('is not set'): '<==>',
    # TRANSLATORS: True if haystack contains needle
    N_('contains'): '=',
    # TRANSLATORS: True if haystack does not contain needle
    N_('does not contain'): '!=',
    # TRANSLATORS: True if haystack contains whole word
    N_('contains word'): 'w=',
    # TRANSLATORS: True if haystack does not contain whole word
    N_('does not contain word'): '!w=',
    # TRANSLATORS: True if haystack matches regular expression
    N_('regex'): '~',
    # TRANSLATORS: True if haystack does not match regular expression
    N_('not regex'): '!~',
    # TRANSLATORS: Example: rating >= 5
    N_('at least'): '>=',
    # TRANSLATORS: Example: rating <= 3
    N_('at most'): '<=',
    # TRANSLATORS: Example: year < 1999
    N_('before'): '<',
    # TRANSLATORS: Example: year > 2002
    N_('after'): '>',
    # TRANSLATORS: Example: 1980 <= year <= 1987
    N_('between'): '><',
    N_('greater than'): '>',
    N_('less than'): '<',
    # TRANSLATORS: Example: track has been added in the last 2 days
    N_('in the last'): '>=',
    # TRANSLATORS: Example: track has not been added in the last 5 hours
    N_('not in the last'): '<',
    # TRANSLATORS: True if a track is contained in the specified playlist
    N_('Track is in'): 'pin',
    # TRANSLATORS: True if a track is not contained in the specified playlist
    N_('Track not in'): '!pin',
}

# This table is a reverse lookup for the actual tag name from a display
# name.
# This gets populated below. Only add special tags/searches here.
_NMAP = {
    N_('Rating'): '__rating',  # special
    N_('Playlist'): '__playlist',  # not a real tag
}

_REV_NMAP = {}


# update the tables based on the globally stored tag list
def __update_maps():

    from xl.metadata.tags import tag_data

    for tag, data in tag_data.items():

        if data is None:
            continue

        # don't catch this KeyError -- if it fails, fix it!
        criteria = _criteria_types[data.type]

        if criteria is None:
            continue

        CRITERIA.append((data.name, criteria))

        _NMAP[data.name] = tag

    for k, v in _NMAP.items():
        if v in _REV_NMAP:
            raise ValueError("_REV_NMAP Internal error: '%s', '%s'" % (k, v))
        _REV_NMAP[v] = k


__update_maps()


class SmartPlaylistEditor:
    @classmethod
    def create(cls, collection, smart_manager, parent=None):
        """
        Shows a dialog to create a new smart playlist

        :param collection:    Collection object
        :param smart_manager: SmartPlaylistManager object
        :param parent:        Dialog parent

        :returns: New smart playlist, or None
        """
        dialog = FilterDialog(_('Add Smart Playlist'), parent, CRITERIA)
        dialog.set_transient_for(parent)

        cls._attach_sort_widgets(dialog, None, None)

        pl = cls._run_edit_dialog(dialog, collection, smart_manager, parent)
        dialog.destroy()
        return pl

    @classmethod
    def edit(cls, pl, collection, smart_manager, parent=None):
        """
        Shows a dialog to edit a smart playlist

        :param collection:    Collection object
        :param smart_manager: SmartPlaylistManager object
        :param parent:        Dialog parent

        :returns: New smart playlist, or None
        """
        if not isinstance(pl, playlist.SmartPlaylist):
            return

        from xl.metadata.tags import tag_data

        params = pl.search_params
        state = []

        for param in params:
            (field, op, value) = param
            rev_field = _REV_NMAP[field]

            # because there are duplicates in _TRANS, cannot create a reverse
            # mapping. Instead, search in set of criteria defined for the type
            data_type = field
            data = tag_data.get(field)
            if data is not None:
                data_type = data.type

            for ct in _criteria_types[data_type]:
                rev_op = ct[0]
                if _TRANS[rev_op] == op:
                    break
            else:
                dialogs.error(parent, "Invalid operand for %s, omitting" % rev_field)
                continue

            state.append(([rev_field, rev_op], value))

        state.reverse()

        dialog = FilterDialog(_('Edit Smart Playlist'), parent, CRITERIA)

        dialog.set_transient_for(parent)
        dialog.set_name(pl.name)
        dialog.set_match_any(pl.get_or_match())
        dialog.set_limit(pl.get_return_limit())
        dialog.set_random(pl.get_random_sort())
        dialog.set_state(state)

        cls._attach_sort_widgets(dialog, *pl.get_sort_tags())

        pl = cls._run_edit_dialog(dialog, collection, smart_manager, parent, orig_pl=pl)
        dialog.destroy()
        return pl

    @classmethod
    def _run_edit_dialog(cls, dialog, collection, smart_manager, parent, orig_pl=None):
        '''internal helper function'''

        while True:
            result = dialog.run()
            dialog.hide()

            if result != Gtk.ResponseType.ACCEPT:
                return

            name = dialog.get_name()
            matchany = dialog.get_match_any()
            limit = dialog.get_limit()
            state = dialog.get_state()
            random = dialog.get_random()
            sort_tags = cls._get_sort_tags(dialog)

            if not name:
                dialogs.error(
                    parent, _("You did " "not enter a name for your playlist")
                )
                continue

            if not orig_pl or name != orig_pl.name:
                try:
                    pl = smart_manager.get_playlist(name)
                    dialogs.error(
                        parent, _("The " "playlist name you entered is already in use.")
                    )
                    continue
                except ValueError:
                    pass  # playlist didn't exist

            pl = playlist.SmartPlaylist(name, collection)
            pl.set_or_match(matchany)
            pl.set_return_limit(limit)
            pl.set_random_sort(random)
            pl.set_sort_tags(*sort_tags)

            for item in state:
                (field, op) = item[0]
                value = item[1]
                pl.add_param(_NMAP[field], _TRANS[op], value)

            if orig_pl:
                smart_manager.remove_playlist(pl.name)

            smart_manager.save_playlist(pl)
            return pl

    @classmethod
    def _attach_sort_widgets(cls, dialog, tag, reverse):
        # Add sort widgets
        from xl.metadata.tags import tag_data

        dialog.sort_enable = sort_enable = Gtk.CheckButton.new_with_label(_('Sort by:'))

        def _on_sort_enable_changed(ck):
            sort_tags.set_sensitive(ck.get_active())
            sort_order.set_sensitive(ck.get_active())

        sort_enable.connect('toggled', _on_sort_enable_changed)

        dialog.sort_tags = sort_tags = Gtk.ComboBoxText.new()
        sort_tags.set_wrap_width(5)
        for k, v in sorted(tag_data.items()):
            if v:
                sort_tags.append(k, v.translated_name)

        dialog.sort_order = sort_order = Gtk.ComboBoxText.new()
        sort_order.append("False", _("Ascending"))
        sort_order.append("True", _("Descending"))

        box = Gtk.Box.new(Gtk.Orientation.HORIZONTAL, 5)
        box.pack_start(sort_enable, False, False, 0)
        box.pack_start(sort_tags, False, False, 0)
        box.pack_start(sort_order, False, False, 0)
        box.show_all()

        dialog.get_content_area().pack_start(box, False, False, 5)

        # Set it up
        if tag is None:
            sort_enable.set_active(False)
            sort_order.set_active_id("False")
        else:
            sort_enable.set_active(True)
            sort_tags.set_active_id(tag)
            sort_order.set_active_id(str(reverse))

        _on_sort_enable_changed(sort_enable)

    @classmethod
    def _get_sort_tags(cls, dialog):
        if not dialog.sort_enable.get_active():
            return None, False
        tag = dialog.sort_tags.get_active_id()
        order = dialog.sort_order.get_active_id() == 'True'
        return tag, order
