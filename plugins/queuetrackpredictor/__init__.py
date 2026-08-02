# Copyright (C) 2026 Exaile contributors
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 2 of the License, or
# (at your option) any later version.

import os
from concurrent.futures import ThreadPoolExecutor
from gi.repository import GLib, Gtk

from xl import player, providers, settings, xdg
from xl.playlist import Playlist
from xl.nls import gettext as _
from xlgui import guiutil, main
from xlgui.widgets import dialogs, menu, notebook, playlist as playlist_widget

from . import model as predictor_model
from . import model_store
from . import preferences as predictor_preferences


MODEL_DIR = 'queuetrackpredictor'
MODEL_FILE = 'models.pickle'
RECENT_TRACK_COUNT = 15
CANDIDATE_POOL_MULTIPLIER = 5
DIVERSITY_REBUILD_DELAY_MS = 200


class QueueTrackPredictorPlugin:
    def __init__(self):
        self.exaile = None
        self.menu_item = None
        self.playlist_menu_item = None
        self.train_dialog = None
        self.model_manager_dialog = None
        self.model_manager_open_source = None
        self.suggestions_playlist = None
        self.suggestions_page = None
        self.suggestions_tab = None
        self.suggestion_request = None
        self.suggestion_generation = 0
        self.suggestion_executor = None
        self.suggestion_future = None
        self.button_registered = False

    def enable(self, exaile):
        self.exaile = exaile
        self.suggestion_executor = ThreadPoolExecutor(
            max_workers=1, thread_name_prefix='track-predictor'
        )

    def get_preferences_pane(self):
        return predictor_preferences

    def on_gui_loaded(self):
        self.menu_item = menu.simple_menu_item(
            'queue-track-predictor-manage',
            ['plugin-sep'],
            _('Manage Track Prediction Models'),
            callback=self.on_manage_models,
        )
        self.menu_item.register('menubar-tools-menu')

        self.playlist_menu_item = PredictionModelsMenuItem(self)
        self.playlist_menu_item.register('playlist-context-menu')

        SuggestNextTrackButton.plugin = self
        providers.register('main-panel-actions', SuggestNextTrackButton)
        self.button_registered = True

    def disable(self, exaile):
        self.suggestion_generation += 1
        if self.model_manager_open_source is not None:
            GLib.source_remove(self.model_manager_open_source)
            self.model_manager_open_source = None
        if self.suggestion_future is not None:
            self.suggestion_future.cancel()
            self.suggestion_future = None
        if self.suggestion_executor is not None:
            self.suggestion_executor.shutdown(wait=False)
            self.suggestion_executor = None
        if self.train_dialog is not None:
            self.train_dialog.destroy()
            self.train_dialog = None
        if self.model_manager_dialog is not None:
            self.model_manager_dialog.destroy()
            self.model_manager_dialog = None
        if self.suggestions_page is not None:
            playlist_notebook = self._get_suggestions_notebook()
            if playlist_notebook is not None:
                playlist_notebook.remove_tab(self.suggestions_tab)
            self._clear_suggestions_tab_references()

        if self.menu_item is not None:
            self.menu_item.unregister()
            self.menu_item = None

        if self.playlist_menu_item is not None:
            self.playlist_menu_item.unregister()
            self.playlist_menu_item = None

        if self.button_registered:
            providers.unregister('main-panel-actions', SuggestNextTrackButton)
            self.button_registered = False
            SuggestNextTrackButton.plugin = None

    def get_model_path(self):
        directory = os.path.join(xdg.get_plugin_data_dir(), MODEL_DIR)
        if not os.path.exists(directory):
            os.makedirs(directory)
        return os.path.join(directory, MODEL_FILE)

    def get_track_groups(self, track):
        if 'grouptagger' not in self.exaile.plugins.enabled_plugins:
            raise RuntimeError(
                _("GroupTagger plugin must be enabled to create or use suggestions.")
            )
        tagname = settings.get_option('plugin/grouptagger/tagname', 'grouping')
        grouping = track.get_tag_raw(tagname, True)
        if grouping is None:
            return set()
        return {group.replace('_', ' ') for group in grouping.split()}

    def _get_parent_window(self, parent=None):
        if parent is not None and hasattr(parent, 'window'):
            return parent.window
        try:
            return main.mainwindow().window
        except Exception:
            return None

    def on_manage_models(self, widget, name, parent, context):
        # Opening a modal window from inside a Gtk.MenuItem activation can cause
        # the provider menu to tear down its children while GTK is still
        # dispatching the event. In particular, this is unsafe on Wayland.
        # Wait until the menu event has completely unwound before changing the
        # active toplevel window.
        if self.model_manager_open_source is not None:
            return
        self.model_manager_open_source = GLib.idle_add(
            self._open_model_manager, self._get_parent_window(parent)
        )

    def _open_model_manager(self, parent_window):
        self.model_manager_open_source = None
        if self.model_manager_dialog is None:
            self.model_manager_dialog = ModelManagerDialog(
                self, parent_window
            )
        self.model_manager_dialog.present()
        return False

    def on_model_manager_destroyed(self, dialog):
        if dialog is self.model_manager_dialog:
            self.model_manager_dialog = None

    def can_suggest_from_playlist_context(self, name, parent, context):
        if context['selection-count'] != 1:
            return False
        selected_items = context['selected-items']
        if not selected_items:
            return False
        return True

    def on_playlist_suggest_next_track(
        self, widget, model_name, parent, context
    ):
        selected_items = context['selected-items']
        if not selected_items:
            return

        position, track = selected_items[0]
        playlist = context['playlist']
        start = max(0, position - (RECENT_TRACK_COUNT - 1))
        previous_tracks = [playlist[idx] for idx in range(start, position + 1)]
        excluded_locations = set()
        if position + 1 < len(playlist):
            excluded_locations.add(playlist[position + 1].get_loc_for_io())
        self.suggest_from_tracks(
            previous_tracks,
            self._get_parent_window(parent),
            excluded_locations=excluded_locations,
            model_name=model_name,
        )

    def load_model_catalog(self):
        return model_store.load_catalog(self.get_model_path())

    def save_model_catalog(self, catalog):
        model_store.save_catalog(self.get_model_path(), catalog)

    def create_model_from_playlists(
        self, name, playlists, playlist_names, included_tags, replace=False
    ):
        model = predictor_model.build_model(
            playlists, self.get_track_groups, included_tags=included_tags
        )
        model['playlist_names'] = sorted(playlist_names)
        catalog = self.load_model_catalog()
        if replace:
            model_store.replace_model(catalog, name, model)
        else:
            model_store.add_model(catalog, name, model)
        self.save_model_catalog(catalog)
        return model

    def load_model(self, model_name=None):
        return self.load_model_entry(model_name)[1]

    def load_model_entry(self, model_name=None):
        catalog = self.load_model_catalog()
        model_name = model_name or catalog.get('selected')
        if model_name is None:
            raise IOError('No prediction model is selected')
        try:
            return model_name, catalog['models'][model_name]
        except KeyError:
            raise ValueError('Prediction model “%s” does not exist' % model_name)

    def suggest_next_track(self, parent_window=None):
        parent_window = parent_window or self._get_parent_window()
        queue_tracks = list(player.QUEUE)
        if len(queue_tracks) < 1:
            dialogs.info(parent_window, _("At least one track must be in the queue."))
            return
        self.suggest_from_tracks(queue_tracks[-RECENT_TRACK_COUNT:], parent_window)

    def suggest_from_tracks(
        self,
        previous_tracks,
        parent_window=None,
        excluded_locations=None,
        model_name=None,
    ):
        parent_window = parent_window or self._get_parent_window()
        previous_tracks = list(previous_tracks)
        excluded_locations = set(excluded_locations or [])
        if len(previous_tracks) < 1:
            dialogs.info(parent_window, _("At least one track is required for suggestions."))
            return

        self.suggestion_request = (
            previous_tracks,
            parent_window,
            excluded_locations,
            model_name,
        )
        max_suggestions = int(
            settings.get_option(
                predictor_preferences.MAX_SUGGESTIONS_OPTION,
                predictor_preferences.DEFAULT_MAX_SUGGESTIONS,
            )
        )
        diversity = int(
            settings.get_option(
                predictor_preferences.DIVERSITY_OPTION,
                predictor_preferences.DEFAULT_DIVERSITY,
            )
        )
        self.suggestion_generation += 1
        generation = self.suggestion_generation
        if self.suggestion_future is not None:
            self.suggestion_future.cancel()
        self.suggestion_future = self.suggestion_executor.submit(
            self._compute_suggestions,
            generation,
            previous_tracks,
            excluded_locations,
            max_suggestions,
            diversity,
            parent_window,
            model_name,
        )

    def _compute_suggestions(
        self,
        generation,
        previous_tracks,
        excluded_locations,
        max_suggestions,
        diversity,
        parent_window,
        model_name,
    ):
        try:
            model_name, trained_model = self.load_model_entry(model_name)
        except IOError:
            GLib.idle_add(
                self._show_suggestion_message,
                generation,
                parent_window,
                False,
                _("Create a track suggestions model first."),
            )
            return
        except Exception as exc:
            GLib.idle_add(
                self._show_suggestion_message,
                generation,
                parent_window,
                True,
                _("Could not load suggestions model: %s") % exc,
            )
            return

        try:
            candidate_limit = max_suggestions * CANDIDATE_POOL_MULTIPLIER
            scored_locations = predictor_model.get_scored_suggestion_locations(
                trained_model,
                previous_tracks,
                self.get_track_groups,
                max_suggestions=candidate_limit,
                excluded_locations=excluded_locations,
            )
            scored_locations = predictor_model.rerank_suggestions_for_diversity(
                trained_model,
                scored_locations,
                previous_tracks[-RECENT_TRACK_COUNT:],
                self.get_track_groups,
                max_suggestions=max_suggestions,
                diversity=diversity,
            )
            scored_tracks = predictor_model.resolve_scored_suggestion_tracks(
                self.exaile.collection,
                scored_locations,
                max_suggestions=max_suggestions,
            )
        except Exception as exc:
            GLib.idle_add(
                self._show_suggestion_message,
                generation,
                parent_window,
                True,
                _("Could not create suggestions: %s") % exc,
            )
            return

        GLib.idle_add(
            self._apply_suggestion_result,
            generation,
            parent_window,
            scored_tracks,
            diversity,
            model_name,
        )

    def _show_suggestion_message(
        self, generation, parent_window, is_error, message
    ):
        if generation != self.suggestion_generation:
            return False
        if is_error:
            dialogs.error(parent_window, message)
        else:
            dialogs.info(parent_window, message)
        return False

    def _apply_suggestion_result(
        self, generation, parent_window, scored_tracks, diversity, model_name
    ):
        if generation != self.suggestion_generation:
            return False
        self.suggestion_future = None
        if not scored_tracks:
            dialogs.info(parent_window, _("No suggestions found for the queue tail."))
            return False
        self.show_suggestions_playlist(scored_tracks, diversity, model_name)
        return False

    def show_suggestions_playlist(self, scored_tracks, diversity, model_name):
        playlist_notebook = self._get_suggestions_notebook()
        if playlist_notebook is None:
            playlist_notebook = main.get_playlist_notebook()
            self.suggestions_playlist = SuggestionsPlaylist(scored_tracks)
            self.suggestions_page = SuggestionsPlaylistPage(
                self,
                self.suggestions_playlist,
                player.PLAYER,
                diversity,
                model_name,
            )
            self.suggestions_page.connect(
                'destroy', self.on_suggestions_page_destroyed
            )
            self.suggestions_tab = notebook.NotebookTab(
                playlist_notebook, self.suggestions_page
            )
            playlist_notebook.add_tab(
                self.suggestions_tab, self.suggestions_page
            )
        else:
            self.suggestions_playlist.replace_tracks(scored_tracks)
            self.suggestions_page.set_diversity(diversity)
            self.suggestions_page.set_model_name(model_name)
            playlist_notebook.set_current_page(
                playlist_notebook.page_num(self.suggestions_page)
            )
            self.suggestions_page.focus()

    def set_suggestion_diversity(self, diversity):
        settings.set_option(
            predictor_preferences.DIVERSITY_OPTION, int(round(diversity))
        )
        if self.suggestion_request is not None:
            self.suggest_from_tracks(*self.suggestion_request)

    def _get_suggestions_notebook(self):
        if self.suggestions_tab is None or self.suggestions_page is None:
            return None
        playlist_notebook = self.suggestions_tab.notebook
        if (
            playlist_notebook is None
            or playlist_notebook.page_num(self.suggestions_page) == -1
        ):
            return None
        return playlist_notebook

    def on_suggestions_page_destroyed(self, page):
        if page is self.suggestions_page:
            self._clear_suggestions_tab_references()

    def _clear_suggestions_tab_references(self):
        self.suggestions_playlist = None
        self.suggestions_page = None
        self.suggestions_tab = None


class PredictionModelsMenuItem(menu.MenuItem):
    def __init__(self, plugin):
        menu.MenuItem.__init__(
            self, 'queue-track-predictor-playlist-suggest', None, ['enqueue']
        )
        self.plugin = plugin

    def factory(self, menu_widget, parent, context):
        if not self.plugin.can_suggest_from_playlist_context(
            self.name, parent, context
        ):
            return None

        item = Gtk.ImageMenuItem.new_with_mnemonic(_('Suggest Next Track'))
        item.set_image(
            Gtk.Image.new_from_icon_name('list-add', Gtk.IconSize.MENU)
        )

        try:
            catalog = self.plugin.load_model_catalog()
            names = model_store.model_names(catalog)
        except Exception:
            names = []

        if not names:
            item.set_sensitive(False)
            return item

        submenu = Gtk.Menu()
        for model_name in names:
            model_item = Gtk.MenuItem.new_with_label(model_name)
            model_item.connect(
                'activate',
                self.plugin.on_playlist_suggest_next_track,
                model_name,
                parent,
                context,
            )
            submenu.append(model_item)
        submenu.show_all()
        item.set_submenu(submenu)
        return item


class SuggestNextTrackButton(Gtk.Button, notebook.NotebookAction):
    plugin = None
    name = 'queue-track-predictor'
    position = Gtk.PackType.END

    def __init__(self, panel_notebook):
        Gtk.Button.__init__(self)
        notebook.NotebookAction.__init__(self, panel_notebook)

        self.set_image(Gtk.Image.new_from_icon_name('list-add', Gtk.IconSize.BUTTON))
        self.set_tooltip_text(_('Suggest Next Track'))
        self.set_focus_on_click(False)
        self.set_relief(Gtk.ReliefStyle.NONE)
        self.connect('clicked', self.on_clicked)
        self.show_all()

    def on_clicked(self, button):
        if self.plugin is not None:
            self.plugin.suggest_next_track()


class SuggestionsPlaylist(Playlist):
    def __init__(self, scored_tracks):
        self.scores = {}
        tracks = self._set_scores(scored_tracks)
        Playlist.__init__(self, _('Track Suggestions'), tracks)

    def replace_tracks(self, scored_tracks):
        tracks = self._set_scores(scored_tracks)
        Playlist.__setitem__(self, slice(None, None, None), tracks)

    def _set_scores(self, scored_tracks):
        scored_tracks = list(scored_tracks)
        self.scores = {
            track.get_loc_for_io(): score for track, score in scored_tracks
        }
        return [track for track, score in scored_tracks]

    def get_score(self, track):
        return self.scores.get(track.get_loc_for_io())

    # The plugin can replace the result set, but user-facing playlist
    # operations must not mutate it.
    def set_shuffle_mode(self, mode):
        pass

    def set_repeat_mode(self, mode):
        pass

    def set_dynamic_mode(self, mode):
        pass

    def randomize(self, positions=None):
        pass

    def sort(self, tags, reverse=False):
        pass

    def clear(self):
        pass

    def __setitem__(self, index, value):
        pass

    def __delitem__(self, index):
        pass

    def append(self, track):
        pass

    def extend(self, tracks):
        pass


class SuggestionsPlaylistView(playlist_widget.PlaylistView):
    def _setup_columns(self):
        playlist_widget.PlaylistView._setup_columns(self)
        score_renderer = Gtk.CellRendererText()
        score_renderer.set_property('xalign', 1.0)
        score_column = Gtk.TreeViewColumn(_('Score'), score_renderer)
        score_column.name = '__queue_predictor_score'
        score_column.set_cell_data_func(score_renderer, self.render_score)
        score_column.set_clickable(False)
        score_column.set_resizable(True)
        score_column.set_sizing(Gtk.TreeViewColumnSizing.FIXED)
        score_column.set_fixed_width(70)
        score_column.set_alignment(1.0)
        self.score_column = score_column
        self.insert_column(score_column, 1)

    def on_columns_changed(self, widget):
        columns = [
            column.name
            for column in self.get_columns()[1:]
            if column is not self.score_column
        ]
        if columns != settings.get_option('gui/columns', []):
            settings.set_option('gui/columns', columns)

    def render_score(self, column, renderer, tree_model, tree_iter, data=None):
        track = tree_model.get_value(tree_iter, 0)
        score = self.playlist.get_score(track)
        renderer.set_property('text', '' if score is None else str(score))


class SuggestionsPlaylistPage(playlist_widget.PlaylistPageBase):
    reorderable = False

    def __init__(
        self,
        plugin,
        suggestions_playlist,
        playlist_player,
        diversity,
        model_name,
    ):
        playlist_widget.PlaylistPageBase.__init__(
            self, suggestions_playlist, playlist_player
        )
        self.plugin = plugin
        self.diversity_rebuild_source = None
        self.swindow = Gtk.ScrolledWindow()
        self.swindow.set_policy(Gtk.PolicyType.AUTOMATIC, Gtk.PolicyType.AUTOMATIC)
        self.view = SuggestionsPlaylistView(
            suggestions_playlist, playlist_player
        )
        self.search_entry = guiutil.SearchEntry()
        self.search_entry.entry.set_size_request(300, -1)
        self.search_entry.entry.set_valign(Gtk.Align.CENTER)
        self.search_entry.entry.set_icon_from_icon_name(
            Gtk.EntryIconPosition.PRIMARY, 'edit-find'
        )
        self.search_entry.entry.set_icon_from_icon_name(
            Gtk.EntryIconPosition.SECONDARY, 'edit-clear'
        )
        self.search_entry.entry.set_icon_sensitive(
            Gtk.EntryIconPosition.PRIMARY, False
        )
        self.search_entry.entry.set_icon_sensitive(
            Gtk.EntryIconPosition.SECONDARY, False
        )
        self.search_entry.entry.set_placeholder_text(_('Search'))
        self.search_entry.entry.connect('activate', self.on_search_entry_activate)
        self.view.set_search_entry(self.search_entry.entry)
        self.view.connect(
            'start-interactive-search',
            lambda *args: self.search_entry.entry.grab_focus(),
        )
        self.view.drag_dest_unset()
        self.swindow.add(self.view)
        self.pack_start(self.swindow, True, True, 0)

        diversity_box = Gtk.Box(spacing=8)
        diversity_box.set_border_width(6)
        self.model_label = Gtk.Label()
        self.model_label.set_xalign(0)
        self.set_model_name(model_name)
        diversity_box.pack_start(self.model_label, False, False, 0)
        separator = Gtk.Separator(orientation=Gtk.Orientation.VERTICAL)
        diversity_box.pack_start(separator, False, False, 0)
        diversity_label = Gtk.Label(label=_('Diversity:'))
        diversity_box.pack_start(diversity_label, False, False, 0)
        self.diversity_scale = Gtk.Scale.new_with_range(
            Gtk.Orientation.HORIZONTAL, 0, 100, 5
        )
        self.diversity_scale.set_hexpand(True)
        self.diversity_scale.set_digits(0)
        self.diversity_scale.add_mark(0, Gtk.PositionType.BOTTOM, _('Prediction'))
        self.diversity_scale.add_mark(100, Gtk.PositionType.BOTTOM, _('Diverse'))
        self.diversity_scale.set_value(diversity)
        self.diversity_scale.connect('value-changed', self.on_diversity_changed)
        diversity_box.pack_start(self.diversity_scale, True, True, 0)
        diversity_box.pack_end(self.search_entry.entry, False, True, 0)
        self.pack_start(diversity_box, False, False, 0)
        self.show_all()

    def focus(self):
        self.view.grab_focus()

    def get_page_name(self):
        return _('Track Suggestions')

    def set_diversity(self, diversity):
        if int(round(self.diversity_scale.get_value())) != int(round(diversity)):
            self.diversity_scale.set_value(diversity)

    def set_model_name(self, model_name):
        self.model_label.set_text(_('Model: %s') % model_name)

    def on_search_entry_activate(self, entry):
        self.view.filter_tracks(entry.get_text() or None)

    def on_diversity_changed(self, scale):
        if self.diversity_rebuild_source is not None:
            GLib.source_remove(self.diversity_rebuild_source)
        self.diversity_rebuild_source = GLib.timeout_add(
            DIVERSITY_REBUILD_DELAY_MS, self.regenerate_suggestions
        )

    def regenerate_suggestions(self):
        self.diversity_rebuild_source = None
        self.plugin.set_suggestion_diversity(self.diversity_scale.get_value())
        return False

    def do_destroy(self):
        if self.diversity_rebuild_source is not None:
            GLib.source_remove(self.diversity_rebuild_source)
            self.diversity_rebuild_source = None
        playlist_widget.PlaylistPageBase.do_destroy(self)


class ModelManagerDialog(Gtk.Dialog):
    def __init__(self, plugin, parent):
        Gtk.Dialog.__init__(
            self,
            title=_('Track Prediction Models'),
            transient_for=parent,
            modal=True,
        )
        self.plugin = plugin
        self.set_default_size(560, 360)
        self.add_button(Gtk.STOCK_CLOSE, Gtk.ResponseType.CLOSE)
        self.connect('response', lambda dialog, response: self.destroy())
        self.connect('destroy', self.plugin.on_model_manager_destroyed)

        self.store = Gtk.ListStore(str, str, str, str)
        self.tree = Gtk.TreeView(model=self.store)
        self.tree.get_selection().set_mode(Gtk.SelectionMode.SINGLE)
        self.tree.get_selection().connect('changed', self.on_selection_changed)
        self.tree.connect('row-activated', self.on_row_activated)
        self.tree.connect('button-press-event', self.on_tree_button_press)
        self._add_text_column('', 0, False)
        self._add_text_column(_('Name'), 1, True)
        self._add_text_column(_('Playlists'), 2, False)
        self._add_text_column(_('Tracks'), 3, False)

        self.context_menu = Gtk.Menu()
        self.context_menu.attach_to_widget(self.tree, None)
        rebuild_menu_item = Gtk.MenuItem(label=_('Rebuild'))
        rebuild_menu_item.connect('activate', self.on_rebuild_clicked)
        self.context_menu.append(rebuild_menu_item)
        self.context_menu.append(Gtk.SeparatorMenuItem())
        remove_menu_item = Gtk.MenuItem(label=_('Remove'))
        remove_menu_item.connect('activate', self.on_remove_clicked)
        self.context_menu.append(remove_menu_item)
        self.context_menu.show_all()

        scroller = Gtk.ScrolledWindow()
        scroller.set_policy(Gtk.PolicyType.AUTOMATIC, Gtk.PolicyType.AUTOMATIC)
        scroller.set_shadow_type(Gtk.ShadowType.ETCHED_IN)
        scroller.add(self.tree)

        buttons = Gtk.Box(spacing=6)
        self.add_button_widget = Gtk.Button(label=_('Add'))
        self.add_button_widget.connect('clicked', self.on_add_clicked)
        buttons.pack_start(self.add_button_widget, False, False, 0)
        self.rebuild_button = Gtk.Button(label=_('Rebuild'))
        self.rebuild_button.connect('clicked', self.on_rebuild_clicked)
        buttons.pack_start(self.rebuild_button, False, False, 0)
        self.rename_button = Gtk.Button(label=_('Rename'))
        self.rename_button.connect('clicked', self.on_rename_clicked)
        buttons.pack_start(self.rename_button, False, False, 0)
        self.remove_button = Gtk.Button(label=_('Remove'))
        self.remove_button.connect('clicked', self.on_remove_clicked)
        buttons.pack_start(self.remove_button, False, False, 0)
        self.select_button = Gtk.Button(label=_('Select'))
        self.select_button.connect('clicked', self.on_select_clicked)
        buttons.pack_end(self.select_button, False, False, 0)

        content = self.get_content_area()
        content.set_border_width(6)
        content.pack_start(scroller, True, True, 0)
        content.pack_start(buttons, False, False, 6)
        self.refresh()
        self.show_all()

    def _add_text_column(self, title, column_id, expand):
        renderer = Gtk.CellRendererText()
        column = Gtk.TreeViewColumn(title, renderer, text=column_id)
        column.set_expand(expand)
        self.tree.append_column(column)

    def refresh(self, select_name=None):
        catalog = self.plugin.load_model_catalog()
        selected_name = catalog.get('selected')
        self.store.clear()
        path_to_select = None
        for name in model_store.model_names(catalog):
            model = catalog['models'][name]
            tree_iter = self.store.append(
                (
                    '\N{BLACK CIRCLE}' if name == selected_name else '',
                    name,
                    str(model.get('playlist_count', 0)),
                    str(model.get('track_count', 0)),
                )
            )
            if name == (select_name or selected_name):
                path_to_select = self.store.get_path(tree_iter)
        if path_to_select is not None:
            self.tree.get_selection().select_path(path_to_select)
        self.on_selection_changed(self.tree.get_selection())

    def get_selected_name(self):
        model, tree_iter = self.tree.get_selection().get_selected()
        return None if tree_iter is None else model[tree_iter][1]

    def on_selection_changed(self, selection):
        enabled = self.get_selected_name() is not None
        self.rebuild_button.set_sensitive(enabled)
        self.rename_button.set_sensitive(enabled)
        self.remove_button.set_sensitive(enabled)
        self.select_button.set_sensitive(enabled)

    def on_add_clicked(self, button):
        name = prompt_for_model_name(self, _('Add Prediction Model'))
        if name is None:
            return
        catalog = self.plugin.load_model_catalog()
        if name in catalog['models']:
            dialogs.error(self, _('A model with that name already exists.'))
            return
        self.plugin.train_dialog = TrainingDialog(self.plugin, self, name)
        self.plugin.train_dialog.present()

    def on_rebuild_clicked(self, button):
        name = self.get_selected_name()
        if name is None:
            return
        catalog = self.plugin.load_model_catalog()
        playlist_names = catalog['models'][name].get('playlist_names', [])
        self.plugin.train_dialog = TrainingDialog(
            self.plugin,
            self,
            name,
            replace=True,
            selected_playlist_names=playlist_names,
        )
        self.plugin.train_dialog.present()

    def on_rename_clicked(self, button):
        old_name = self.get_selected_name()
        if old_name is None:
            return
        new_name = prompt_for_model_name(self, _('Rename Prediction Model'), old_name)
        if new_name is None:
            return
        catalog = self.plugin.load_model_catalog()
        try:
            model_store.rename_model(catalog, old_name, new_name)
        except ValueError as exc:
            dialogs.error(self, str(exc))
            return
        self.plugin.save_model_catalog(catalog)
        self.refresh(new_name)

    def on_remove_clicked(self, button):
        name = self.get_selected_name()
        if name is None:
            return
        response = dialogs.yesno(
            self, _('Remove the prediction model “%s”?') % name
        )
        if response != Gtk.ResponseType.YES:
            return
        catalog = self.plugin.load_model_catalog()
        model_store.remove_model(catalog, name)
        self.plugin.save_model_catalog(catalog)
        self.refresh()

    def on_select_clicked(self, button):
        name = self.get_selected_name()
        if name is None:
            return
        catalog = self.plugin.load_model_catalog()
        model_store.select_model(catalog, name)
        self.plugin.save_model_catalog(catalog)
        self.refresh(name)

    def on_row_activated(self, tree, path, column):
        self.tree.get_selection().select_path(path)
        self.on_select_clicked(None)

    def on_tree_button_press(self, tree, event):
        if event.button != 3:
            return False
        row = tree.get_path_at_pos(int(event.x), int(event.y))
        if row is None:
            return False
        tree.get_selection().select_path(row[0])
        self.context_menu.popup_at_pointer(event)
        return True

def prompt_for_model_name(parent, title, initial=''):
    dialog = Gtk.Dialog(title=title, transient_for=parent, modal=True)
    dialog.add_buttons(
        Gtk.STOCK_CANCEL,
        Gtk.ResponseType.CANCEL,
        Gtk.STOCK_OK,
        Gtk.ResponseType.OK,
    )
    entry = Gtk.Entry()
    entry.set_text(initial)
    entry.set_activates_default(True)
    dialog.set_default_response(Gtk.ResponseType.OK)
    content = dialog.get_content_area()
    content.set_border_width(12)
    content.pack_start(Gtk.Label(label=_('Model name:')), False, False, 0)
    content.pack_start(entry, False, False, 6)
    dialog.show_all()
    response = dialog.run()
    name = entry.get_text().strip() if response == Gtk.ResponseType.OK else None
    dialog.destroy()
    if response == Gtk.ResponseType.OK and not name:
        dialogs.error(parent, _('Model name cannot be empty.'))
        return None
    return name


class TrainingDialog(Gtk.Dialog):
    def __init__(
        self,
        plugin,
        parent,
        model_name,
        replace=False,
        selected_playlist_names=None,
    ):
        self.action = _('Rebuild') if replace else _('Create')
        Gtk.Dialog.__init__(
            self,
            title=_('%(action)s Prediction Model “%(name)s”')
            % {'action': self.action, 'name': model_name},
            transient_for=parent,
            modal=True,
        )
        self.plugin = plugin
        self.model_name = model_name
        self.replace = replace
        self.selected_playlist_names = set(selected_playlist_names or [])
        self.page = 'playlists'
        self.set_default_size(420, 360)
        self.add_buttons(
            Gtk.STOCK_CANCEL,
            Gtk.ResponseType.CANCEL,
            Gtk.STOCK_GO_BACK,
            Gtk.ResponseType.APPLY,
            _('Next'),
            Gtk.ResponseType.OK,
        )
        self.back_button = self.get_widget_for_response(Gtk.ResponseType.APPLY)
        self.primary_button = self.get_widget_for_response(Gtk.ResponseType.OK)
        self.set_default_response(Gtk.ResponseType.OK)
        self.connect('response', self.on_response)
        self.connect('delete-event', self.on_delete_event)

        content = self.get_content_area()
        content.set_border_width(6)
        self.playlist_page = Gtk.Box(orientation=Gtk.Orientation.VERTICAL)
        self.tag_page = Gtk.Box(orientation=Gtk.Orientation.VERTICAL)
        content.pack_start(self.playlist_page, True, True, 0)
        content.pack_start(self.tag_page, True, True, 0)

        label = Gtk.Label(label=_('Select saved playlists to analyze.'))
        label.set_xalign(0)
        self.playlist_page.pack_start(label, False, False, 0)

        select_box = Gtk.Box(spacing=6)
        self.select_all_button = Gtk.Button(label=_('Select All'))
        self.select_all_button.connect('clicked', self.on_select_all_clicked)
        select_box.pack_start(self.select_all_button, False, False, 0)
        self.playlist_page.pack_start(select_box, False, False, 4)

        self.playlist_store = Gtk.ListStore(bool, str, object)
        self.playlist_tree = Gtk.TreeView(model=self.playlist_store)
        self.playlist_tree.set_headers_visible(True)

        toggle = Gtk.CellRendererToggle()
        toggle.connect('toggled', self.on_playlist_toggled)
        toggle_column = Gtk.TreeViewColumn('', toggle, active=0)
        self.playlist_tree.append_column(toggle_column)

        text = Gtk.CellRendererText()
        name_column = Gtk.TreeViewColumn(_('Playlist'), text, text=1)
        name_column.set_expand(True)
        self.playlist_tree.append_column(name_column)

        scroller = Gtk.ScrolledWindow()
        scroller.set_policy(Gtk.PolicyType.AUTOMATIC, Gtk.PolicyType.AUTOMATIC)
        scroller.set_shadow_type(Gtk.ShadowType.ETCHED_IN)
        scroller.add(self.playlist_tree)
        self.playlist_page.pack_start(scroller, True, True, 6)

        tag_label = Gtk.Label(
            label=_('Select GroupTagger tags to include in the prediction model.')
        )
        tag_label.set_xalign(0)
        self.tag_page.pack_start(tag_label, False, False, 0)

        tag_buttons = Gtk.Box(spacing=6)
        select_all_tags = Gtk.Button(label=_('Select All'))
        select_all_tags.connect(
            'clicked', lambda button: self.set_all_tags_selected(True)
        )
        tag_buttons.pack_start(select_all_tags, False, False, 0)
        deselect_all_tags = Gtk.Button(label=_('Deselect All'))
        deselect_all_tags.connect(
            'clicked', lambda button: self.set_all_tags_selected(False)
        )
        tag_buttons.pack_start(deselect_all_tags, False, False, 0)
        self.tag_page.pack_start(tag_buttons, False, False, 4)

        self.tag_store = Gtk.ListStore(bool, str)
        self.tag_tree = Gtk.TreeView(model=self.tag_store)
        self.tag_tree.set_headers_visible(True)
        tag_toggle = Gtk.CellRendererToggle()
        tag_toggle.connect('toggled', self.on_tag_toggled)
        self.tag_tree.append_column(
            Gtk.TreeViewColumn('', tag_toggle, active=0)
        )
        tag_text = Gtk.CellRendererText()
        tag_column = Gtk.TreeViewColumn(_('Tag'), tag_text, text=1)
        tag_column.set_expand(True)
        self.tag_tree.append_column(tag_column)

        tag_scroller = Gtk.ScrolledWindow()
        tag_scroller.set_policy(
            Gtk.PolicyType.AUTOMATIC, Gtk.PolicyType.AUTOMATIC
        )
        tag_scroller.set_shadow_type(Gtk.ShadowType.ETCHED_IN)
        tag_scroller.add(self.tag_tree)
        self.tag_page.pack_start(tag_scroller, True, True, 6)

        self.status = Gtk.Label()
        self.status.set_xalign(0)
        content.pack_start(self.status, False, False, 0)

        self.populate_playlists()
        self.show_all()
        self.show_playlist_page()

    def populate_playlists(self):
        manager = self.plugin.exaile.playlists
        for name in sorted(manager.list_playlists()):
            self.playlist_store.append(
                (
                    name in self.selected_playlist_names,
                    name,
                    manager.get_playlist(name),
                )
            )

    def on_playlist_toggled(self, renderer, path):
        self.playlist_store[path][0] = not self.playlist_store[path][0]

    def on_select_all_clicked(self, button):
        for row in self.playlist_store:
            row[0] = True

    def get_selected_playlists(self):
        return [row[2] for row in self.playlist_store if row[0]]

    def get_selected_playlist_names(self):
        return [row[1] for row in self.playlist_store if row[0]]

    def show_playlist_page(self):
        self.page = 'playlists'
        self.status.set_text('')
        self.tag_page.hide()
        self.playlist_page.show_all()
        self.back_button.hide()
        self.primary_button.set_label(_('Next'))

    def show_tag_page(self):
        playlists = self.get_selected_playlists()
        if not playlists:
            self.status.set_text(_('Select at least one playlist.'))
            return False

        try:
            tags = predictor_model.get_playlist_tags(
                playlists, self.plugin.get_track_groups
            )
        except Exception as exc:
            dialogs.error(self, _('Could not read playlist tags: %s') % exc)
            return False

        excluded_tags = set(
            settings.get_option(predictor_preferences.EXCLUDED_TAGS_OPTION, [])
        )
        self.tag_store.clear()
        for tag in sorted(tags, key=str.casefold):
            self.tag_store.append((tag not in excluded_tags, tag))

        self.page = 'tags'
        self.status.set_text(
            ''
            if tags
            else _('No GroupTagger tags found; the model will use BPM only.')
        )
        self.playlist_page.hide()
        self.tag_page.show_all()
        self.back_button.show()
        self.primary_button.set_label(self.action)
        return True

    def on_tag_toggled(self, renderer, path):
        row = self.tag_store[path]
        row[0] = not row[0]
        self.remember_tag_selection(row[1], row[0])

    def set_all_tags_selected(self, selected):
        excluded_tags = set(
            settings.get_option(predictor_preferences.EXCLUDED_TAGS_OPTION, [])
        )
        for row in self.tag_store:
            row[0] = selected
            if selected:
                excluded_tags.discard(row[1])
            else:
                excluded_tags.add(row[1])
        settings.set_option(
            predictor_preferences.EXCLUDED_TAGS_OPTION, sorted(excluded_tags)
        )

    def remember_tag_selection(self, tag, selected):
        excluded_tags = set(
            settings.get_option(predictor_preferences.EXCLUDED_TAGS_OPTION, [])
        )
        if selected:
            excluded_tags.discard(tag)
        else:
            excluded_tags.add(tag)
        settings.set_option(
            predictor_preferences.EXCLUDED_TAGS_OPTION, sorted(excluded_tags)
        )

    def get_selected_tags(self):
        return [row[1] for row in self.tag_store if row[0]]

    def on_response(self, dialog, response):
        if response == Gtk.ResponseType.APPLY and self.page == 'tags':
            self.show_playlist_page()
            return
        if response != Gtk.ResponseType.OK:
            self.destroy()
            return
        if self.page == 'playlists':
            self.show_tag_page()
            return

        try:
            trained_model = self.plugin.create_model_from_playlists(
                self.model_name,
                self.get_selected_playlists(),
                self.get_selected_playlist_names(),
                self.get_selected_tags(),
                replace=self.replace,
            )
        except Exception as exc:
            dialogs.error(self, _("Could not create suggestions model: %s") % exc)
            return

        dialogs.info(
            self,
            _(
                "%(action)s model from %(playlists)d playlist(s) and "
                "%(tracks)d track(s)."
            )
            % {
                'action': _('Rebuilt') if self.replace else _('Created'),
                'playlists': trained_model.get('playlist_count', 0),
                'tracks': trained_model.get('track_count', 0),
            },
        )
        if self.plugin.model_manager_dialog is not None:
            self.plugin.model_manager_dialog.refresh(self.model_name)

        self.destroy()

    def on_delete_event(self, widget, event):
        self.plugin.train_dialog = None

    def destroy(self):
        self.plugin.train_dialog = None
        Gtk.Dialog.destroy(self)


plugin_class = QueueTrackPredictorPlugin
