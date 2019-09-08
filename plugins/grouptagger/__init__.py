# Copyright (C) 2011 Dustin Spicuzza
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
from gi.repository import Pango

from xl import event, providers, player, settings

from xl.nls import gettext as _

from xlgui.widgets import menu, dialogs

from . import gt_prefs
from . import gt_widgets
from .gt_common import (
    migrate_settings,
    get_group_categories,
    set_group_categories,
    get_track_groups,
    set_track_groups,
    create_all_search_playlist,
    tagname_option,
    create_custom_search_playlist,
)
from . import gt_export
from . import gt_import
from . import gt_mass


class GroupTaggerPlugin:
    '''Implements logic for plugin'''

    def get_preferences_pane(self):
        return gt_prefs

    def enable(self, exaile):
        self.exaile = exaile

    def on_gui_loaded(self):

        self.track = None
        self.tag_dialog = None

        migrate_settings()

        self.panel = gt_widgets.GroupTaggerPanel(self.exaile)
        self.panel.show_all()
        self.setup_panel_font(False)

        self.panel.tagger.view.connect('category-changed', self.on_category_change)
        self.panel.tagger.view.connect('category-edited', self.on_category_edited)
        self.panel.tagger.view.connect('group-changed', self.on_group_change)

        # add to exaile's panel interface
        providers.register('main-panel', self.panel)

        # ok, register for some events
        event.add_ui_callback(self.on_playback_track_start, 'playback_track_start')
        event.add_ui_callback(
            self.on_playlist_cursor_changed, 'playlist_cursor_changed'
        )
        event.add_ui_callback(
            self.on_plugin_options_set, 'plugin_grouptagger_option_set'
        )

        # add our own submenu for functionality
        tools_submenu = menu.Menu(None, context_func=lambda p: self.exaile)

        tools_submenu.add_item(
            menu.simple_menu_item(
                'gt_get_tags',
                [],
                _('_Get all tags from collection'),
                callback=self.on_get_tags_menu,
            )
        )

        tools_submenu.add_item(
            menu.simple_menu_item(
                'gt_import',
                [],
                _('_Import tags from directory'),
                callback=self.on_import_tags,
            )
        )

        tools_submenu.add_item(
            menu.simple_menu_item(
                'gt_rename',
                [],
                _('_Mass rename/delete tags'),
                callback=self.on_mass_rename,
            )
        )

        tools_submenu.add_item(
            menu.simple_menu_item(
                'gt_export',
                [],
                _('E_xport collecton tags to JSON'),
                callback=self.on_export_tags,
            )
        )

        # group them together to make it not too long
        self.tools_menuitem = menu.simple_menu_item(
            'grouptagger', ['plugin-sep'], _('_GroupTagger'), submenu=tools_submenu
        )
        providers.register('menubar-tools-menu', self.tools_menuitem)

        # playlist context menu items
        self.provider_items = []
        track_subitem = menu.Menu(None, inherit_context=True)

        track_subitem.add_item(
            menu.simple_menu_item(
                'gt_search_all',
                [],
                _('Show tracks with all tags'),
                callback=self.on_playlist_context_select_all_menu,
                callback_args=[self.exaile],
            )
        )

        track_subitem.add_item(
            menu.simple_menu_item(
                'gt_search_custom',
                ['gt_search_all'],
                _('Show tracks with tags (custom)'),
                callback=self.on_playlist_context_select_custom_menu,
                callback_args=[self.exaile],
            )
        )

        tag_cond_fn = lambda n, p, c: c['selection-count'] > 1

        track_subitem.add_item(
            menu.simple_menu_item(
                'gt_tag_add_multi',
                ['gt_search_custom'],
                _('Add tags to all'),
                callback=self.on_add_tags,
                condition_fn=tag_cond_fn,
                callback_args=[self.exaile],
            )
        )

        track_subitem.add_item(
            menu.simple_menu_item(
                'gt_tag_rm_multi',
                ['gt_tag_add_multi'],
                _('Remove tags from all'),
                callback=self.on_rm_tags,
                condition_fn=tag_cond_fn,
                callback_args=[self.exaile],
            )
        )

        self.provider_items.append(
            menu.simple_menu_item(
                'grouptagger', ['rating'], _('GroupTagger'), submenu=track_subitem
            )
        )

        for item in self.provider_items:
            providers.register('playlist-context-menu', item)
            # Hm, doesn't work..
            # providers.register('track-panel-menu', item)

        # trigger start event if exaile is currently playing something
        if player.PLAYER.is_playing():
            self.set_display_track(player.PLAYER.current)
        else:
            self.panel.tagger.set_categories([], get_group_categories())

    def disable(self, exaile):
        '''Called when the plugin is disabled'''

        if self.tools_menuitem:
            providers.unregister('menubar-tools-menu', self.tools_menuitem)
            for item in self.provider_items:
                providers.unregister('playlist-context-menu', item)
                providers.unregister('track-panel-menu', item)

            self.tools_menuitem = None
            self.provider_items = []

        if self.tag_dialog:
            self.tag_dialog.destroy()
            self.tag_dialog = None

        # de-register the exaile events
        event.remove_callback(self.on_playback_track_start, 'playback_track_start')
        event.remove_callback(
            self.on_playlist_cursor_changed, 'playlist_cursor_changed'
        )
        event.remove_callback(
            self.on_plugin_options_set, 'plugin_grouptagger_option_set'
        )

        providers.unregister('main-panel', self.panel)

    def setup_panel_font(self, always_set):
        font = settings.get_option('plugin/grouptagger/panel_font', None)
        if font is None:
            if not always_set:
                return
            font = gt_prefs._get_system_default_font()
        else:
            font = Pango.FontDescription(font)

        self.panel.tagger.set_font(font)

    #
    # Menu callbacks
    #

    def on_export_tags(self, widget, name, parent, exaile):
        gt_export.export_tags(exaile)

    def on_get_tags_menu(self, widget, name, parent, exaile):

        if self.tag_dialog is None:
            self.tag_dialog = gt_widgets.AllTagsDialog(
                exaile, self.panel.tagger.add_groups
            )
            self.tag_dialog.connect(
                'delete-event', self.on_get_tags_menu_window_deleted
            )

        self.tag_dialog.show_all()

    def on_get_tags_menu_window_deleted(self, *args):
        self.tag_dialog = None

    def on_import_tags(self, widget, name, parent, exaile):
        gt_import.import_tags(exaile)

    def on_mass_rename(self, widget, name, parent, exaile):
        gt_mass.mass_rename(exaile)

    def _add_rm_multi_tags(self, add, context, exaile):
        '''Add or remove tags from multiple tracks'''
        tracks = context['selected-tracks']

        dialog = gt_widgets.GroupTaggerAddRemoveDialog(add, tracks, exaile)
        if add:
            dialog.tagger.set_categories([], get_group_categories())
        else:
            groups = set()
            for track in tracks:
                groups |= get_track_groups(track)
            dialog.tagger.add_groups(groups)

        # TODO: something more dynamic
        dialog.set_size_request(250, 500)

        retval = dialog.run()

        groups = {}

        if retval == Gtk.ResponseType.APPLY:
            groups = set(dialog.get_active())

        dialog.destroy()

        if len(groups) > 0:
            for track in tracks:
                existing = get_track_groups(track)
                if add:
                    set_track_groups(track, existing | groups)
                else:
                    set_track_groups(track, existing - groups)

    def on_add_tags(self, widget, name, parent, context, exaile):
        self._add_rm_multi_tags(True, context, exaile)

    def on_rm_tags(self, widget, name, parent, context, exaile):
        self._add_rm_multi_tags(False, context, exaile)

    #
    # Exaile events
    #

    def on_playback_track_start(self, type, player, track):
        '''Called when a new track starts'''
        self.set_display_track(track)

    def on_playlist_context_select_all_menu(
        self, menu, display_name, playlist_view, context, exaile
    ):
        '''Called when 'Select tracks with same tags' is selected'''
        tracks = context['selected-tracks']
        groups = set()

        for track in tracks:
            groups |= get_track_groups(track)

        if len(groups) > 0:
            create_all_search_playlist(groups, exaile)
        else:
            dialogs.error(None, _('No categorization tags found in selected tracks'))

    def on_playlist_context_select_custom_menu(
        self, menu, display_name, playlist_view, context, exaile
    ):
        '''Called when 'select tracks with similar tags (custom)' is selected'''
        tracks = context['selected-tracks']
        groups = set()

        for track in tracks:
            groups |= get_track_groups(track)

        if len(groups) > 0:
            create_custom_search_playlist(groups, exaile)
        else:
            dialogs.error(None, _('No categorization tags found in selected tracks'))

    def on_playlist_cursor_changed(self, type, playlist_view, context):
        '''Called when an item in a playlist is selected'''

        # TODO: Allow multiple tracks
        tracks = context['selected-tracks']
        if len(tracks) == 1:
            self.set_display_track(tracks[0])

    def set_display_track(self, track, force_update=False):
        '''Updates the display with the tags/info for a particular track'''

        if self.track == track and not force_update:
            return

        self.track = track

        # get the groups as a set
        track_groups = get_track_groups(track)

        # set them
        self.panel.tagger.view.show_click_column()
        self.panel.tagger.set_categories(track_groups, get_group_categories())
        self.panel.tagger.set_track_info(track)

    #
    # Widget events
    #

    def on_category_change(self, view, action, category):
        '''Called when a category has something happen to it'''

        categories = get_group_categories()

        if action == gt_widgets.category_change.added:
            categories.setdefault(category, [True, []])

        elif action == gt_widgets.category_change.deleted:
            del categories[category]

        elif action == gt_widgets.category_change.collapsed:
            categories[category][0] = False

        elif action == gt_widgets.category_change.expanded:
            categories[category][0] = True

        elif action == gt_widgets.category_change.updated:
            v = categories.setdefault(category, [True, []])
            v[1] = view.get_model().get_category_groups(category)

        set_group_categories(categories)

    def on_category_edited(self, view, old_category, new_category):
        '''Called when a category name is edited'''

        categories = get_group_categories()
        categories[new_category] = categories.pop(old_category)
        set_group_categories(categories)

    def on_group_change(self, view, action, value):
        '''Called when a group is added/deleted/updated on the widget'''

        if self.track is not None:
            groups = view.get_model().iter_active()
            if not set_track_groups(self.track, groups):
                self.set_display_track(self.track, force_update=True)

    def on_plugin_options_set(self, evtype, settings, option):
        '''Handles option changes'''
        if option == 'plugin/grouptagger/panel_font':
            self.setup_panel_font(True)
        elif option == tagname_option:
            if self.track is not None:
                self.set_display_track(self.track, True)


plugin_class = GroupTaggerPlugin
