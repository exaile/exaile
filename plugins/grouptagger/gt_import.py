from gi.repository import Gtk

from xl.common import idle_add, SimpleProgressThread
from xl.collection import Collection, Library, CollectionScanThread
from xl.nls import gettext as _
from xl.trax import search_tracks, TracksMatcher

from xlgui.progress import ProgressManager
from xlgui.widgets import dialogs

from xlgui.guiutil import GtkTemplate

from .gt_common import get_track_groups, set_track_groups

import logging

logger = logging.getLogger(__name__)


@GtkTemplate('gt_import.ui', relto=__file__)
class GtImporter(Gtk.Window):
    """
    Shows a dialog that allows importing of grouping tags
    from a directory not included in the current collection.
    """

    __gtype_name__ = 'GtImporter'

    (
        content_area,
        ok_button,
        tags_model,
        tags_view,
        tags_vbox,
        radio_merge,
        radio_replace,
    ) = GtkTemplate.Child.widgets(7)

    def __init__(self, exaile, uris):
        Gtk.Window.__init__(self, transient_for=exaile.gui.main.window)
        self.init_template()

        self.exaile = exaile

        self.collection = Collection("GT Import Collection")

        for uri in uris:
            self.collection.add_library(Library(uri))

        self.manager = ProgressManager(self.content_area)

        self.rescan_thread = CollectionScanThread(self.collection)
        self.rescan_thread.connect('done', self._on_rescan_done)

        self.import_thread = None

        self.manager.add_monitor(
            self.rescan_thread, _("Importing tracks"), 'document-open'
        )

    #
    # Status routines
    #

    @idle_add()
    def _on_rescan_done(self, thread):
        '''Called when the collection is finished loading'''

        if self.rescan_thread is None:
            return

        self.rescan_thread = None

        logger.info('Import directory scan completed, importing groups')

        # now that the collection has loaded, import the groups from them
        self.import_track_data = []
        self.import_thread = SimpleProgressThread(
            track_import_thread,
            self.collection,
            self.exaile.collection,
            self.import_track_data,
        )
        self.import_thread.connect('done', self._on_import_done)
        self.manager.add_monitor(
            self.import_thread, _("Importing groups"), 'document-open'
        )

    @idle_add()
    def _on_import_done(self, thread):
        '''Called when the grouping data is retrieved'''

        if self.import_thread is None:
            return

        track_data = self.import_track_data
        self.import_thread = None
        self.import_track_data = None

        logger.info('Group import finished, %s new tracks found', len(track_data))

        if len(track_data) == 0:
            self.destroy()

            locations = ';'.join(
                [l.get_location() for l in self.collection.get_libraries()]
            )

            dialogs.info(
                self.exaile.gui.main.window, 'No new tracks found at "%s"' % locations
            )
            return

        self.tags_view.freeze_child_notify()
        self.tags_view.set_model(None)

        # add the data to the model
        for old_group_str, new_group_str, matched_track, newgroups in track_data:
            self.tags_model.append(
                (
                    True,
                    str(matched_track),
                    old_group_str,
                    new_group_str,
                    matched_track,
                    newgroups,
                )
            )

        self.tags_view.set_model(self.tags_model)
        self.tags_view.thaw_child_notify()

        self.ok_button.set_sensitive(True)
        self.tags_vbox.set_visible(True)

    @idle_add()
    def _on_update_done(self, thread):

        if self.update_thread is None:
            return

        self.update_thread = None

        logger.info('Track update complete')
        self.destroy()

    #
    # Widget events
    #

    @GtkTemplate.Callback
    def on_cancel_button_clicked(self, widget):

        if self.rescan_thread is not None:
            self.rescan_thread.stop()
        elif self.import_thread is not None:
            self.import_thread.stop()
        elif self.update_thread is not None:
            self.update_thread.stop()

        self.destroy()

    @GtkTemplate.Callback
    def on_import_checkbox_toggled(self, cell, path):
        self.tags_model[path][0] = not cell.get_active()

    @GtkTemplate.Callback
    def on_ok_button_clicked(self, widget):

        self.ok_button.set_sensitive(False)
        self.tags_vbox.set_sensitive(False)

        data = [(row[4], row[5]) for row in self.tags_model if row[0]]
        logger.info('Updating %s tracks', len(data))

        self.update_thread = SimpleProgressThread(
            track_update_thread, data, self.radio_replace.get_active()
        )
        self.update_thread.connect('done', self._on_update_done)

        self.manager.add_monitor(self.update_thread, _("Updating groups"), 'system-run')

    @GtkTemplate.Callback
    def on_window_destroy(self, widget):
        self.collection.close()


def track_import_thread(import_collection, user_collection, track_data):
    """
    Reads grouping information from tracks in a collection, and matches
    them with tracks contained in a separate collection.
    """

    total = float(len(import_collection))

    # to import, all essential fields should be identical!
    fields = ['__length', 'artist', 'album', 'title', 'genre', 'tracknumber']

    logger.info("Finding matches for %s imported tracks", len(import_collection))

    exact_dups = 0
    no_change = 0

    # determine which tracks in this collection match existing
    # tracks in the exaile collection. grab the groups from them
    for i, track in enumerate(import_collection):

        # search for a matching track
        # -> currently exaile doesn't index tracks, and linear searches
        #    for the track instead. Oh well.

        matchers = [TracksMatcher(track.get_tag_search(t)) for t in fields]
        matched_tracks = [r.track for r in search_tracks(user_collection, matchers)]

        # if there are matches, add the data to the track data
        for matched_track in matched_tracks:

            # ignore exact duplicates
            if track is matched_track:
                exact_dups += 1
                continue

            old_group_str = ' '.join(get_track_groups(matched_track))
            newgroups = get_track_groups(track)
            new_group_str = ' '.join(newgroups)

            if old_group_str == new_group_str:
                no_change += 1
                continue

            track_data.append((old_group_str, new_group_str, matched_track, newgroups))

        yield (i, total)

    logger.info(
        "Match information: %s exact dups, %s no change, %s differing tracks",
        exact_dups,
        no_change,
        len(track_data),
    )


def track_update_thread(trackdata, replace):
    """
    Sets new groups on a set of tracks
    """
    total = len(trackdata)

    for i, (curtrack, newgroups) in enumerate(trackdata):

        if replace:
            set_track_groups(curtrack, newgroups)
        else:
            curgroups = get_track_groups(curtrack) | newgroups
            set_track_groups(curtrack, curgroups)

        yield (i, total)


def import_tags(exaile):
    """
    Function to show a dialog that allows the user to import grouping
    tags from a directory of their choosing.
    """

    def _on_uris_selected(widget, uris):
        import_dialog = GtImporter(exaile, uris)
        import_dialog.show()

    file_dialog = dialogs.DirectoryOpenDialog(
        exaile.gui.main.window, title=_('Select directory to import grouping tags from')
    )
    file_dialog.connect('uris-selected', _on_uris_selected)
    file_dialog.run()
    file_dialog.destroy()
