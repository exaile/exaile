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
from xl.nls import gettext as _, ngettext
from xlgui import guiutil, main
from xlgui.accelerators import Accelerator
from xlgui.widgets import dialogs, menu, notebook, playlist as playlist_widget

from . import model as predictor_model
from . import model_store
from . import preferences as predictor_preferences


MODEL_DIR = 'queuetrackpredictor'
MODEL_FILE = 'models.pickle'
RECENT_TRACK_COUNT = 15
CANDIDATE_POOL_MULTIPLIER = 5
DIVERSITY_REBUILD_DELAY_MS = 200
TAG_BIAS_REBUILD_DELAY_MS = 250
BPM_BIAS_REBUILD_DELAY_MS = 250
TAG_BIAS_LABELS = {
    -2: _('Strongly away'),
    -1: _('Away'),
    0: _('Neutral'),
    1: _('Toward'),
    2: _('Strongly toward'),
}


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
        self.suggest_accelerator = None
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
        providers.register('playlist-notebook-actions', SuggestNextTrackButton)
        self.button_registered = True
        self.suggest_accelerator = Accelerator(
            '<Primary><Shift>g',
            _('Suggest Next Track'),
            self.on_suggest_accelerator,
        )
        providers.register('mainwindow-accelerators', self.suggest_accelerator)

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
            providers.unregister(
                'playlist-notebook-actions', SuggestNextTrackButton
            )
            self.button_registered = False
            SuggestNextTrackButton.plugin = None
        if self.suggest_accelerator is not None:
            providers.unregister(
                'mainwindow-accelerators', self.suggest_accelerator
            )
            self.suggest_accelerator = None

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

        position = selected_items[-1][0]
        self.suggest_after_playlist_position(
            context['playlist'],
            position,
            self._get_parent_window(parent),
            model_name,
        )

    def suggest_after_playlist_position(
        self, playlist, position, parent_window=None, model_name=None
    ):
        start = max(0, position - (RECENT_TRACK_COUNT - 1))
        previous_tracks = [playlist[idx] for idx in range(start, position + 1)]
        excluded_locations = set()
        if position + 1 < len(playlist):
            excluded_locations.add(playlist[position + 1].get_loc_for_io())
        self.suggest_from_tracks(
            previous_tracks,
            parent_window or self._get_parent_window(),
            excluded_locations=excluded_locations,
            model_name=model_name,
        )

    def suggest_from_current_page(self, page=None):
        page = page or main.get_selected_page()
        view = getattr(page, 'view', None)
        playlist = getattr(page, 'playlist', None)
        selected_items = view.get_selected_items() if view is not None else []
        if playlist is not None and selected_items:
            position = selected_items[-1][0]
            self.suggest_after_playlist_position(playlist, position)
            return
        self.suggest_next_track()

    def on_suggest_accelerator(self, *args):
        self.suggest_from_current_page()
        return True

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
        if not replace:
            self.set_last_model_name(name)
        return model

    def _get_model_tuning_settings(self):
        tuning = settings.get_option(
            predictor_preferences.MODEL_TUNING_OPTION, {}
        )
        return tuning if isinstance(tuning, dict) else {}

    def get_model_tuning(self, model_name, model=None, all_tuning=None):
        model = model or self.load_model(model_name)
        all_tuning = (
            self._get_model_tuning_settings()
            if all_tuning is None
            else all_tuning
        )
        tuning = all_tuning.get(model_name, {})
        return predictor_model.normalize_model_tuning(model, tuning)

    def _set_model_tuning(self, model_name, tag_biases=None, bpm_bias=None):
        model = self.load_model(model_name)
        all_tuning = dict(self._get_model_tuning_settings())
        tuning = self.get_model_tuning(model_name, model, all_tuning)
        if tag_biases is not None:
            tuning['tag_biases'] = tag_biases
        if bpm_bias is not None:
            tuning['bpm_bias'] = predictor_model.clamp_bpm_bias(bpm_bias)
        tuning = self.get_model_tuning(
            model_name, model, {model_name: tuning}
        )
        if tuning['tag_biases'] or tuning['bpm_bias'] != 0:
            all_tuning[model_name] = tuning
        else:
            all_tuning.pop(model_name, None)
        settings.set_option(
            predictor_preferences.MODEL_TUNING_OPTION, all_tuning
        )

    def set_model_tag_biases(self, model_name, tag_biases):
        self._set_model_tuning(model_name, tag_biases=tag_biases)

    def set_model_bpm_bias(self, model_name, bpm_bias):
        self._set_model_tuning(model_name, bpm_bias=bpm_bias)

    def get_default_model_name(self, catalog=None):
        catalog = catalog or self.load_model_catalog()
        model_name = settings.get_option(
            predictor_preferences.LAST_MODEL_OPTION, ''
        )
        if model_name in catalog['models']:
            return model_name
        selected = catalog.get('selected')
        if selected in catalog['models']:
            return selected
        return next(iter(model_store.model_names(catalog)), None)

    def set_last_model_name(self, model_name):
        settings.set_option(predictor_preferences.LAST_MODEL_OPTION, model_name)

    def rename_model_settings(self, old_name, new_name):
        all_tuning = dict(self._get_model_tuning_settings())
        if old_name in all_tuning:
            all_tuning[new_name] = all_tuning.pop(old_name)
            settings.set_option(
                predictor_preferences.MODEL_TUNING_OPTION, all_tuning
            )
        if (
            settings.get_option(predictor_preferences.LAST_MODEL_OPTION, '')
            == old_name
        ):
            self.set_last_model_name(new_name)

    def remove_model_settings(self, model_name, catalog):
        all_tuning = dict(self._get_model_tuning_settings())
        if model_name in all_tuning:
            del all_tuning[model_name]
            settings.set_option(
                predictor_preferences.MODEL_TUNING_OPTION, all_tuning
            )
        if (
            settings.get_option(predictor_preferences.LAST_MODEL_OPTION, '')
            == model_name
        ):
            self.set_last_model_name(
                self.get_default_model_name(catalog) or ''
            )

    def load_model(self, model_name=None):
        return self.load_model_entry(model_name)[1]

    def load_model_entry(self, model_name=None):
        catalog = self.load_model_catalog()
        model_name = model_name or self.get_default_model_name(catalog)
        if model_name is None:
            raise IOError('No prediction model is selected')
        try:
            return model_name, catalog['models'][model_name]
        except KeyError:
            raise ValueError('Prediction model “%s” does not exist' % model_name)

    def remember_used_model(self, model_name):
        if (
            settings.get_option(predictor_preferences.LAST_MODEL_OPTION, '')
            == model_name
        ):
            return
        self.set_last_model_name(model_name)

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
        model_tuning = self._get_model_tuning_settings()
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
            model_tuning,
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
        model_tuning,
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
            runtime_model = dict(trained_model)
            runtime_model.update(
                self.get_model_tuning(
                    model_name, trained_model, model_tuning
                )
            )
            candidate_tracks = self.exaile.collection.get_tracks()
            candidate_features = predictor_model.make_candidate_features(
                candidate_tracks,
                self.get_track_groups,
                runtime_model.get(
                    'bpm_band_size', predictor_model.DEFAULT_BPM_BAND_SIZE
                ),
                runtime_model.get('included_tags'),
            )
            candidate_limit = max_suggestions * CANDIDATE_POOL_MULTIPLIER
            scored_locations = predictor_model.get_scored_suggestion_locations(
                runtime_model,
                previous_tracks,
                self.get_track_groups,
                max_suggestions=candidate_limit,
                excluded_locations=excluded_locations,
                candidate_features=candidate_features,
            )
            scored_locations = predictor_model.rerank_suggestions_for_diversity(
                runtime_model,
                scored_locations,
                previous_tracks[-RECENT_TRACK_COUNT:],
                self.get_track_groups,
                max_suggestions=max_suggestions,
                diversity=diversity,
                candidate_features=candidate_features,
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
        try:
            self.remember_used_model(model_name)
        except Exception as exc:
            dialogs.error(
                parent_window,
                _('Could not remember the last suggestion model: %s') % exc,
            )
        if not scored_tracks:
            dialogs.info(parent_window, _("No suggestions found for the queue tail."))
            return False
        if self.suggestion_request is not None:
            previous_tracks, request_parent, excluded_locations, _ = (
                self.suggestion_request
            )
            self.suggestion_request = (
                previous_tracks,
                request_parent,
                excluded_locations,
                model_name,
            )
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

    def __init__(self, playlist_notebook):
        Gtk.Button.__init__(self)
        notebook.NotebookAction.__init__(self, playlist_notebook)

        self.set_image(Gtk.Image.new_from_icon_name('list-add', Gtk.IconSize.BUTTON))
        self.set_has_tooltip(True)
        self.set_focus_on_click(False)
        self.set_relief(Gtk.ReliefStyle.NONE)
        self.connect('clicked', self.on_clicked)
        self.connect('query-tooltip', self.on_query_tooltip)
        self.show_all()

    def on_clicked(self, button):
        if self.plugin is not None:
            self.plugin.suggest_from_current_page(self.notebook.get_current_tab())

    def on_query_tooltip(self, widget, x, y, keyboard_mode, tooltip):
        page = self.notebook.get_current_tab()
        view = getattr(page, 'view', None)
        count = view.get_selection_count() if view is not None else 0
        shortcut = Gtk.accelerator_get_label(
            self.plugin.suggest_accelerator.key,
            self.plugin.suggest_accelerator.mods,
        )
        if count == 1:
            text = _('Suggest after selected track (%s)') % shortcut
        elif count > 1:
            text = _('Suggest after last selected track (%s)') % shortcut
        else:
            text = _('Suggest from queue (%s)') % shortcut
        tooltip.set_text(text)
        return True


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
        if score is None:
            text = ''
        elif float(score).is_integer():
            text = str(int(score))
        else:
            text = '%.1f' % score
        renderer.set_property('text', text)


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
        self.tag_rebuild_source = None
        self.bpm_rebuild_source = None
        self.model_name = None
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

        self.content_stack = Gtk.Stack()
        self.content_stack.set_transition_type(
            Gtk.StackTransitionType.CROSSFADE
        )
        self.content_stack.add_named(self.swindow, 'suggestions')
        self._build_tag_tuning_panel()
        self.pack_start(self.content_stack, True, True, 0)

        diversity_box = Gtk.Box(spacing=8)
        diversity_box.set_border_width(6)
        self.model_label = Gtk.Label()
        self.model_label.set_xalign(0)
        diversity_box.pack_start(self.model_label, False, False, 0)
        self.tuning_toggle = Gtk.ToggleButton(label=_('Tune Tags'))
        self.tuning_toggle.set_tooltip_text(
            _('Tune tag preferences for this prediction model')
        )
        self.tuning_toggle.connect('toggled', self.on_tuning_toggled)
        diversity_box.pack_start(self.tuning_toggle, False, False, 0)
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
        bpm_separator = Gtk.Separator(orientation=Gtk.Orientation.VERTICAL)
        diversity_box.pack_start(bpm_separator, False, False, 0)
        bpm_label = Gtk.Label(label=_('BPM bias:'))
        diversity_box.pack_start(bpm_label, False, False, 0)
        self.bpm_bias_scale = Gtk.Scale.new_with_range(
            Gtk.Orientation.HORIZONTAL,
            -predictor_model.BPM_BIAS_FULL_EFFECT_DELTA,
            predictor_model.BPM_BIAS_FULL_EFFECT_DELTA,
            5,
        )
        self.bpm_bias_scale.set_hexpand(True)
        self.bpm_bias_scale.set_digits(0)
        self.bpm_bias_scale.set_draw_value(True)
        self.bpm_bias_scale.add_mark(
            -predictor_model.BPM_BIAS_FULL_EFFECT_DELTA,
            Gtk.PositionType.BOTTOM,
            _('Slower'),
        )
        self.bpm_bias_scale.add_mark(0, Gtk.PositionType.BOTTOM, _('Neutral'))
        self.bpm_bias_scale.add_mark(
            predictor_model.BPM_BIAS_FULL_EFFECT_DELTA,
            Gtk.PositionType.BOTTOM,
            _('Faster'),
        )
        self.bpm_bias_scale.set_tooltip_text(
            _('Favor tracks slower or faster than the latest track')
        )
        self.bpm_bias_changed_id = self.bpm_bias_scale.connect(
            'value-changed', self.on_bpm_bias_changed
        )
        self.bpm_bias_scale.connect('format-value', self.format_bpm_bias_value)
        diversity_box.pack_start(self.bpm_bias_scale, True, True, 0)
        diversity_box.pack_end(self.search_entry.entry, False, True, 0)
        self.pack_start(diversity_box, False, False, 0)
        self.set_model_name(model_name)
        self.content_stack.set_visible_child_name('suggestions')
        self.show_all()

    def _build_tag_tuning_panel(self):
        panel = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=6)
        panel.set_border_width(8)

        tools = Gtk.Box(spacing=6)
        self.tag_search = Gtk.SearchEntry()
        self.tag_search.set_placeholder_text(_('Search tags'))
        self.tag_search.set_hexpand(True)
        self.tag_search.connect('search-changed', self.on_tag_filter_changed)
        tools.pack_start(self.tag_search, True, True, 0)

        self.tag_filter_choice = Gtk.ComboBoxText()
        self.tag_filter_choice.append('all', _('All'))
        self.tag_filter_choice.append('adjusted', _('Adjusted'))
        self.tag_filter_choice.append('neutral', _('Neutral'))
        self.tag_filter_choice.set_active_id('all')
        self.tag_filter_choice.connect('changed', self.on_tag_filter_changed)
        tools.pack_start(self.tag_filter_choice, False, False, 0)

        self.tag_sort_choice = Gtk.ComboBoxText()
        self.tag_sort_choice.append('adjusted', _('Adjusted First'))
        self.tag_sort_choice.append('name', _('Name'))
        self.tag_sort_choice.append('bias', _('Bias'))
        self.tag_sort_choice.set_active_id('adjusted')
        self.tag_sort_choice.set_tooltip_text(_('Sort tags'))
        self.tag_sort_choice.connect('changed', self.on_tag_sort_changed)
        tools.pack_start(self.tag_sort_choice, False, False, 0)

        self.reset_all_tags_button = Gtk.Button(label=_('Reset Tags'))
        self.reset_all_tags_button.connect('clicked', self.on_reset_all_tags)
        tools.pack_start(self.reset_all_tags_button, False, False, 0)
        panel.pack_start(tools, False, False, 0)

        self.tag_biases = {}
        self.tag_children = {}
        self.tag_bias_labels = {}
        self.tag_tuning_flow = Gtk.FlowBox()
        self.tag_tuning_flow.set_selection_mode(Gtk.SelectionMode.MULTIPLE)
        self.tag_tuning_flow.set_activate_on_single_click(False)
        self.tag_tuning_flow.set_column_spacing(6)
        self.tag_tuning_flow.set_row_spacing(6)
        self.tag_tuning_flow.set_homogeneous(False)
        self.tag_tuning_flow.set_min_children_per_line(1)
        self.tag_tuning_flow.set_max_children_per_line(20)
        self.tag_tuning_flow.set_valign(Gtk.Align.START)
        self.tag_tuning_flow.set_filter_func(self.is_tag_child_visible)
        self.tag_tuning_flow.set_sort_func(self.compare_tag_children)
        self.tag_tuning_flow.connect(
            'selected-children-changed', self.on_tag_selection_changed
        )
        self.tag_tuning_flow.connect(
            'child-activated', self.on_tag_child_activated
        )
        self.tag_tuning_flow.connect('key-press-event', self.on_tag_key_pressed)

        tag_scroller = Gtk.ScrolledWindow()
        tag_scroller.set_policy(
            Gtk.PolicyType.AUTOMATIC, Gtk.PolicyType.AUTOMATIC
        )
        tag_scroller.set_shadow_type(Gtk.ShadowType.ETCHED_IN)
        tag_scroller.add(self.tag_tuning_flow)
        panel.pack_start(tag_scroller, True, True, 0)

        self.tag_selection_label = Gtk.Label(label=_('Select one or more tags.'))
        self.tag_selection_label.set_xalign(0)
        panel.pack_start(self.tag_selection_label, False, False, 0)

        self.bias_buttons = Gtk.Box(spacing=4)
        for shortcut, bias in enumerate((-2, -1, 0, 1, 2), 1):
            button = Gtk.Button(label=TAG_BIAS_LABELS[bias])
            button.set_tooltip_text(
                _('Apply to selected tags (keyboard shortcut: %d)') % shortcut
            )
            button.connect(
                'clicked',
                lambda widget, value=bias: self.set_selected_tag_bias(value),
            )
            self.bias_buttons.pack_start(button, True, True, 0)
        self.bias_buttons.set_sensitive(False)
        panel.pack_start(self.bias_buttons, False, False, 0)

        self.content_stack.add_named(panel, 'tuning')

    def focus(self):
        if not self.tuning_toggle.get_active():
            self.view.grab_focus()

    def on_tuning_toggled(self, button):
        tuning = button.get_active()
        self.content_stack.set_visible_child_name(
            'tuning' if tuning else 'suggestions'
        )
        self.search_entry.entry.set_visible(not tuning)
        if tuning:
            button.set_label(_('Show Suggestions'))
            self.tag_search.grab_focus()
        else:
            self._update_tuning_button_label()
            self.view.grab_focus()

    def _populate_tag_tuning(self, model):
        tuning = self.plugin.get_model_tuning(self.model_name, model)
        bpm_bias = tuning['bpm_bias']
        self.bpm_bias_scale.handler_block(self.bpm_bias_changed_id)
        self.bpm_bias_scale.set_value(bpm_bias)
        self.bpm_bias_scale.handler_unblock(self.bpm_bias_changed_id)
        included_tags = model.get('included_tags')
        if included_tags is None:
            included_tags = {
                tag
                for summary in model.get('candidate_features', {}).values()
                for tag in summary.get('groups', ())
            }
        else:
            included_tags = set(included_tags)
        self.tag_biases = {
            tag: int(bias)
            for tag, bias in tuning['tag_biases'].items()
            if tag in included_tags
            and bias in predictor_model.TAG_BIAS_FACTORS
            and bias != 0
        }
        for child in self.tag_tuning_flow.get_children():
            self.tag_tuning_flow.remove(child)
        self.tag_children.clear()
        self.tag_bias_labels.clear()
        for tag in included_tags:
            child = Gtk.FlowBoxChild()
            tile = Gtk.Box(spacing=8)
            tile.set_border_width(8)
            tile.set_size_request(180, -1)
            tag_label = Gtk.Label(label=tag)
            tag_label.set_xalign(0)
            tag_label.set_hexpand(True)
            bias_label = Gtk.Label(
                label=TAG_BIAS_LABELS[self.tag_biases.get(tag, 0)]
            )
            bias_label.set_xalign(1)
            self._set_tag_bias_label(bias_label, self.tag_biases.get(tag, 0))
            tile.pack_start(tag_label, True, True, 0)
            tile.pack_end(bias_label, False, False, 0)
            child.add(tile)
            self.tag_children[child] = tag
            self.tag_bias_labels[tag] = bias_label
            self.tag_tuning_flow.insert(child, -1)
            child.show_all()
        self.tag_tuning_flow.invalidate_filter()
        self.tag_tuning_flow.invalidate_sort()
        has_tags = bool(self.tag_children)
        self.tuning_toggle.set_sensitive(True)
        self.reset_all_tags_button.set_sensitive(bool(self.tag_biases))
        self.tag_selection_label.set_text(
            _('Select one or more tags.')
            if has_tags
            else _('This model does not include any tags.')
        )
        self._update_tuning_button_label()

    def is_tag_child_visible(self, child, data=None):
        tag = self.tag_children[child]
        bias = self.tag_biases.get(tag, 0)
        query = self.tag_search.get_text().strip().casefold()
        if query and query not in tag.casefold():
            return False
        mode = self.tag_filter_choice.get_active_id() or 'all'
        if mode == 'adjusted':
            return bias != 0
        if mode == 'neutral':
            return bias == 0
        return True

    def on_tag_filter_changed(self, widget):
        self.tag_tuning_flow.unselect_all()
        self.tag_tuning_flow.invalidate_filter()

    def compare_tag_children(self, first, second, data=None):
        first_tag = self.tag_children[first]
        second_tag = self.tag_children[second]
        first_bias = self.tag_biases.get(first_tag, 0)
        second_bias = self.tag_biases.get(second_tag, 0)
        mode = self.tag_sort_choice.get_active_id() or 'adjusted'
        if mode == 'name':
            first_key = (first_tag.casefold(), first_tag)
            second_key = (second_tag.casefold(), second_tag)
        elif mode == 'bias':
            first_key = (-first_bias, first_tag.casefold(), first_tag)
            second_key = (-second_bias, second_tag.casefold(), second_tag)
        else:
            first_key = (
                first_bias == 0,
                first_tag.casefold(),
                first_tag,
            )
            second_key = (
                second_bias == 0,
                second_tag.casefold(),
                second_tag,
            )
        return (first_key > second_key) - (first_key < second_key)

    def on_tag_sort_changed(self, widget):
        self.tag_tuning_flow.invalidate_sort()

    def on_tag_selection_changed(self, flowbox):
        count = len(flowbox.get_selected_children())
        self.bias_buttons.set_sensitive(count > 0)
        self.tag_selection_label.set_text(
            ngettext('%d tag selected.', '%d tags selected.', count) % count
            if count
            else _('Select one or more tags.')
        )

    def _selected_tag_names(self):
        return [
            self.tag_children[child]
            for child in self.tag_tuning_flow.get_selected_children()
        ]

    def _set_tag_bias_label(self, label, bias):
        label.set_text(TAG_BIAS_LABELS[bias])
        context = label.get_style_context()
        if bias == 0:
            context.add_class('dim-label')
        else:
            context.remove_class('dim-label')

    def set_selected_tag_bias(self, bias):
        selected = set(self._selected_tag_names())
        if not selected:
            return
        for tag in selected:
            if bias == 0:
                self.tag_biases.pop(tag, None)
            else:
                self.tag_biases[tag] = bias
            self._set_tag_bias_label(self.tag_bias_labels[tag], bias)
        self._tag_biases_changed()

    def on_tag_child_activated(self, flowbox, child):
        tag = self.tag_children[child]
        bias = self.tag_biases.get(tag, 0)
        levels = (-2, -1, 0, 1, 2)
        next_bias = levels[(levels.index(bias) + 1) % len(levels)]
        self.set_selected_tag_bias(next_bias)

    def on_tag_key_pressed(self, flowbox, event):
        bias_for_key = {'1': -2, '2': -1, '3': 0, '4': 1, '5': 2, '0': 0}
        bias = bias_for_key.get(event.string)
        if bias is None:
            return False
        self.set_selected_tag_bias(bias)
        return True

    def on_reset_all_tags(self, button):
        if self.tag_biases:
            self.tag_biases.clear()
            for label in self.tag_bias_labels.values():
                self._set_tag_bias_label(label, 0)
            self._tag_biases_changed()

    def _tag_biases_changed(self):
        try:
            self.plugin.set_model_tag_biases(self.model_name, self.tag_biases)
        except Exception as exc:
            dialogs.error(
                self.plugin._get_parent_window(),
                _('Could not save tag tuning: %s') % exc,
            )
            self._populate_tag_tuning(self.plugin.load_model(self.model_name))
            return
        self.tag_tuning_flow.invalidate_filter()
        self.tag_tuning_flow.invalidate_sort()
        self.reset_all_tags_button.set_sensitive(bool(self.tag_biases))
        self._update_tuning_button_label()
        if self.tag_rebuild_source is not None:
            GLib.source_remove(self.tag_rebuild_source)
        self.tag_rebuild_source = GLib.timeout_add(
            TAG_BIAS_REBUILD_DELAY_MS, self.regenerate_tag_suggestions
        )

    def _update_tuning_button_label(self):
        if not hasattr(self, 'tuning_toggle'):
            return
        if self.tuning_toggle.get_active():
            self.tuning_toggle.set_label(_('Show Suggestions'))
            return
        adjusted = len(self.tag_biases)
        self.tuning_toggle.set_label(
            _('Tune Tags (%d)') % adjusted if adjusted else _('Tune Tags')
        )

    def on_bpm_bias_changed(self, scale):
        if self.bpm_rebuild_source is not None:
            GLib.source_remove(self.bpm_rebuild_source)
        self.bpm_rebuild_source = GLib.timeout_add(
            BPM_BIAS_REBUILD_DELAY_MS, self.regenerate_bpm_suggestions
        )

    def format_bpm_bias_value(self, scale, value):
        value = int(round(value))
        if value < 0:
            return _('%d BPM slower') % abs(value)
        if value > 0:
            return _('%d BPM faster') % value
        return _('Neutral')

    def regenerate_bpm_suggestions(self):
        self.bpm_rebuild_source = None
        try:
            self.plugin.set_model_bpm_bias(
                self.model_name, self.bpm_bias_scale.get_value()
            )
        except Exception as exc:
            dialogs.error(
                self.plugin._get_parent_window(),
                _('Could not save BPM tuning: %s') % exc,
            )
            self._populate_tag_tuning(self.plugin.load_model(self.model_name))
            return False
        if self.plugin.suggestion_request is not None:
            self.plugin.suggest_from_tracks(*self.plugin.suggestion_request)
        return False

    def regenerate_tag_suggestions(self):
        self.tag_rebuild_source = None
        if self.plugin.suggestion_request is not None:
            self.plugin.suggest_from_tracks(*self.plugin.suggestion_request)
        return False

    def get_page_name(self):
        return _('Track Suggestions')

    def set_diversity(self, diversity):
        if int(round(self.diversity_scale.get_value())) != int(round(diversity)):
            self.diversity_scale.set_value(diversity)

    def set_model_name(self, model_name):
        self.model_label.set_text(_('Model: %s') % model_name)
        if model_name == self.model_name:
            return
        self.model_name = model_name
        try:
            model = self.plugin.load_model(model_name)
        except Exception:
            self.tag_biases.clear()
            for child in self.tag_tuning_flow.get_children():
                self.tag_tuning_flow.remove(child)
            self.tag_children.clear()
            self.tag_bias_labels.clear()
            self.tuning_toggle.set_sensitive(False)
            self.reset_all_tags_button.set_sensitive(False)
            self._update_tuning_button_label()
            return
        self._populate_tag_tuning(model)

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
        if self.tag_rebuild_source is not None:
            GLib.source_remove(self.tag_rebuild_source)
            self.tag_rebuild_source = None
        if self.bpm_rebuild_source is not None:
            GLib.source_remove(self.bpm_rebuild_source)
            self.bpm_rebuild_source = None
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
        selected_name = self.plugin.get_default_model_name(catalog)
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
        self.plugin.rename_model_settings(old_name, new_name)
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
        self.plugin.remove_model_settings(name, catalog)
        self.refresh()

    def on_select_clicked(self, button):
        name = self.get_selected_name()
        if name is None:
            return
        self.plugin.set_last_model_name(name)
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
