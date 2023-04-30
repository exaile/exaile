# Copyright (C) 2010 Adam Olsen
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

from xl import xdg, main, metadata, settings
from xl.nls import gettext as _
from xlgui.preferences import widgets
from xlgui import progress
from xl.common import SimpleProgressThread

name = _('Collection')
icon = 'folder-music'
ui = xdg.get_data_path('ui', 'preferences', 'collection.ui')


def _get_default_strip_list():
    return []
    # FIXME:  currently, this is broken by the backend not also having access
    # to the default set here, so we will just NOT set one.

    # TRANSLATORS: Grammatical articles that are ignored while sorting the
    # collection panel. For example, in French locales this could be
    # the space-separated list "l' la le les".
    # If this practice is not common in your locale, simply
    # translate this to string with single space.
    default_strip_list = _("the")
    return [v.lower() for v in default_strip_list.split(' ') if v]


class CollectionStripArtistPreference(widgets.ListPreference):
    default = _get_default_strip_list()
    name = 'collection/strip_list'

    def __init__(self, preferences, widget):
        widgets.ListPreference.__init__(self, preferences, widget)
        self.widget.connect('populate-popup', self._populate_popup_cb)

    def _get_value(self):
        """
        Get the value, overrides the base class function
        because we don't need shlex parsing. We actually
        want values like "l'" here.
        """
        values = [v.lower() for v in self.widget.get_text().split(' ') if v]
        return values

    def _populate_popup_cb(self, entry, menu):
        from gi.repository import Gtk

        entry = Gtk.MenuItem.new_with_mnemonic(_('Reset to _Defaults'))
        entry.connect('activate', self._reset_to_defaults_cb)
        entry.show()

        sep = Gtk.SeparatorMenuItem()
        sep.show()

        menu.attach(entry, 0, 1, 0, 1)
        menu.attach(sep, 0, 1, 1, 2)

    def _reset_to_defaults_cb(self, item):
        self.widget.set_text(' '.join(_get_default_strip_list()))


class FileBasedCompilationsPreference(widgets.CheckPreference):
    default = True
    name = 'collection/file_based_compilations'


class WriteRatingToAudioFileMetadataPreference(widgets.CheckPreference):
    default = False
    name = 'collection/write_rating_to_audio_file_metadata'


class WriteRatingToAudioFileMetadataPOPMemail(widgets.Preference, widgets.Conditional):
    default = ""
    name = 'collection/write_rating_to_audio_file_metadata_popm_mail'
    condition_preference_name = 'collection/write_rating_to_audio_file_metadata'

    def __init__(self, preferences, widget):
        widgets.Preference.__init__(self, preferences, widget)
        widgets.Conditional.__init__(self)

    def on_check_condition(self):
        return self.condition_widget.get_active() is True


class WriteRatingToAudioFileMetadataSyncNow(widgets.Button, widgets.Conditional):
    default = ""
    name = "collection/write_rating_to_audio_file_metadata_sync_now"
    condition_preference_name = 'collection/write_rating_to_audio_file_metadata'

    def __init__(self, preferences, widget):
        widgets.Button.__init__(self, preferences, widget)
        widgets.Conditional.__init__(self)
        self.progress = None
        self.scan_thread = None
        self.monitor = None

    def on_check_condition(self):
        return self.condition_widget.get_active() is True

    def on_clicked(self, button):
        if self.progress:
            return

        curr_page = self.preferences.last_page
        box = self.preferences.builders[curr_page].get_object(
            'collection/write_rating_to_audio_file_metadata_progress'
        )
        self.progress = progress.ProgressManager(box)

        self.scan_thread = SimpleProgressThread(
            self.track_scan,
        )
        self.scan_thread.connect('done', self.on_done)
        self.monitor = self.progress.add_monitor(
            self.scan_thread,
            _("Migrating ratings to audio file metadata"),
            'document-open',
        )

        box.show()

    def track_scan(self):
        exaile = main.exaile()
        collection = exaile.collection
        total = len(collection.tracks)
        i = 0

        for track in collection.tracks:
            trax = collection.tracks[track]
            format_data = metadata.get_format(track)

            if '__rating' in format_data.tag_mapping:
                rating = trax.get_rating()
                if rating > 0:
                    trax.set_rating(rating)

            i += 1
            yield i, total

    def on_done(self, a):
        self.progress.remove_monitor(self.monitor)
        self.progress = None


class UseLegacyMetadataMappingPreference(widgets.CheckPreference):
    default = False
    name = 'collection/use_legacy_metadata_mapping'


class UseLegacyMetadataMappingSyncNow(widgets.Button, widgets.Conditional):
    default = ""
    name = "collection/use_legacy_metadata_mapping_sync_now"
    condition_preference_name = 'collection/use_legacy_metadata_mapping'

    def __init__(self, preferences, widget):
        widgets.Button.__init__(self, preferences, widget)
        widgets.Conditional.__init__(self)
        self.progress = None
        self.scan_thread = None
        self.monitor = None

    def on_check_condition(self):
        return self.condition_widget.get_active() is True

    def on_clicked(self, button):
        if self.progress:
            return

        curr_page = self.preferences.last_page
        box = self.preferences.builders[curr_page].get_object(
            'collection/use_legacy_metadata_mapping_progress'
        )
        self.progress = progress.ProgressManager(box)

        self.scan_thread = SimpleProgressThread(
            self.track_scan,
        )
        self.scan_thread.connect('done', self.on_done)
        self.monitor = self.progress.add_monitor(
            self.scan_thread,
            _("Migrating metadata"),
            'document-open',
        )

        box.show()

    def track_scan(self):
        from xl.metadata import flac, ogg

        exaile = main.exaile()
        collection = exaile.collection
        total = len(collection.tracks)
        i = 0

        for track in collection.tracks:
            trax = collection.tracks[track]
            format_data = metadata.get_format(track)

            if not isinstance(format_data, flac.FlacFormat) and not isinstance(
                format_data, ogg.OggFormat
            ):
                continue

            settings.set_option('collection/use_legacy_metadata_mapping', True)
            bpm = trax.get_tag_disk('tempo')
            comment = trax.get_tag_disk('description')

            settings.set_option('collection/use_legacy_metadata_mapping', False)
            trax.set_tag_disk('bpm', bpm)
            trax.set_tag_disk('comment', comment)

            i += 1
            yield i, total

    def on_done(self, a):
        self.progress.remove_monitor(self.monitor)
        self.progress = None
        settings.set_option('collection/use_legacy_metadata_mapping', False)
        self.condition_widget.set_active(False)


# vim:ts=4 et sw=4
