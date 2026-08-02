# Copyright (C) 2026 Exaile contributors
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 2 of the License, or
# (at your option) any later version.

import os
from gi.repository import Gtk

from xl import player, providers, settings, xdg
from xl.nls import gettext as _
from xlgui import main
from xlgui.widgets import dialogs, menu, notebook

from . import model as predictor_model
from . import model_store


MODEL_DIR = 'queuetrackpredictor'
MODEL_FILE = 'models.pickle'


class QueueTrackPredictorPlugin:
    def __init__(self):
        self.exaile = None
        self.menu_item = None
        self.playlist_menu_item = None
        self.train_dialog = None
        self.model_manager_dialog = None
        self.suggestion_dialog = None
        self.button_registered = False

    def enable(self, exaile):
        self.exaile = exaile

    def on_gui_loaded(self):
        self.menu_item = menu.simple_menu_item(
            'queue-track-predictor-manage',
            ['plugin-sep'],
            _('Manage Track Prediction Models'),
            callback=self.on_manage_models,
        )
        self.menu_item.register('menubar-tools-menu')

        self.playlist_menu_item = menu.simple_menu_item(
            'queue-track-predictor-playlist-suggest',
            ['enqueue'],
            _('Suggest Next Track'),
            'list-add',
            callback=self.on_playlist_suggest_next_track,
            condition_fn=self.can_suggest_from_playlist_context,
        )
        self.playlist_menu_item.register('playlist-context-menu')

        SuggestNextTrackButton.plugin = self
        providers.register('main-panel-actions', SuggestNextTrackButton)
        self.button_registered = True

    def disable(self, exaile):
        if self.train_dialog is not None:
            self.train_dialog.destroy()
            self.train_dialog = None
        if self.model_manager_dialog is not None:
            self.model_manager_dialog.destroy()
            self.model_manager_dialog = None
        if self.suggestion_dialog is not None:
            self.suggestion_dialog.destroy()
            self.suggestion_dialog = None

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
        if self.model_manager_dialog is None:
            self.model_manager_dialog = ModelManagerDialog(
                self, self._get_parent_window(parent)
            )
        self.model_manager_dialog.present()

    def can_suggest_from_playlist_context(self, name, parent, context):
        if context['selection-count'] != 1:
            return False
        selected_items = context['selected-items']
        if not selected_items:
            return False
        return True

    def on_playlist_suggest_next_track(self, widget, name, parent, context):
        selected_items = context['selected-items']
        if not selected_items:
            return

        position, track = selected_items[0]
        playlist = context['playlist']
        start = max(0, position - 2)
        previous_tracks = [playlist[idx] for idx in range(start, position + 1)]
        excluded_locations = set()
        if position + 1 < len(playlist):
            excluded_locations.add(playlist[position + 1].get_loc_for_io())
        self.suggest_from_tracks(
            previous_tracks,
            self._get_parent_window(parent),
            excluded_locations=excluded_locations,
        )

    def load_model_catalog(self):
        return model_store.load_catalog(self.get_model_path())

    def save_model_catalog(self, catalog):
        model_store.save_catalog(self.get_model_path(), catalog)

    def create_model_from_playlists(self, name, playlists):
        model = predictor_model.build_model(playlists, self.get_track_groups)
        catalog = self.load_model_catalog()
        model_store.add_model(catalog, name, model)
        self.save_model_catalog(catalog)
        return model

    def load_model(self):
        catalog = self.load_model_catalog()
        selected = catalog.get('selected')
        if selected is None:
            raise IOError('No prediction model is selected')
        return catalog['models'][selected]

    def suggest_next_track(self, parent_window=None):
        parent_window = parent_window or self._get_parent_window()
        queue_tracks = list(player.QUEUE)
        if len(queue_tracks) < 1:
            dialogs.info(parent_window, _("At least one track must be in the queue."))
            return
        self.suggest_from_tracks(queue_tracks[-3:], parent_window)

    def suggest_from_tracks(
        self, previous_tracks, parent_window=None, excluded_locations=None
    ):
        parent_window = parent_window or self._get_parent_window()
        try:
            trained_model = self.load_model()
        except IOError:
            dialogs.info(parent_window, _("Create a track suggestions model first."))
            return
        except Exception as exc:
            dialogs.error(parent_window, _("Could not load suggestions model: %s") % exc)
            return

        if len(previous_tracks) < 1:
            dialogs.info(parent_window, _("At least one track is required for suggestions."))
            return

        try:
            locations = predictor_model.get_suggestion_locations(
                trained_model,
                previous_tracks[-3:],
                self.get_track_groups,
                excluded_locations=excluded_locations,
            )
        except Exception as exc:
            dialogs.error(parent_window, _("Could not create suggestions: %s") % exc)
            return

        tracks = predictor_model.resolve_suggestion_tracks(
            self.exaile.collection, locations
        )

        if not tracks:
            dialogs.info(parent_window, _("No suggestions found for the queue tail."))
            return

        if self.suggestion_dialog is not None:
            self.suggestion_dialog.destroy()

        self.suggestion_dialog = SuggestionsDialog(self, parent_window, tracks)
        self.suggestion_dialog.present()

    def append_to_queue(self, track):
        player.QUEUE.append(track)


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
        self.connect('delete-event', self.on_delete_event)

        self.store = Gtk.ListStore(str, str, str, str)
        self.tree = Gtk.TreeView(model=self.store)
        self.tree.get_selection().set_mode(Gtk.SelectionMode.SINGLE)
        self.tree.get_selection().connect('changed', self.on_selection_changed)
        self.tree.connect('row-activated', self.on_row_activated)
        self._add_text_column('', 0, False)
        self._add_text_column(_('Name'), 1, True)
        self._add_text_column(_('Playlists'), 2, False)
        self._add_text_column(_('Tracks'), 3, False)

        scroller = Gtk.ScrolledWindow()
        scroller.set_policy(Gtk.PolicyType.AUTOMATIC, Gtk.PolicyType.AUTOMATIC)
        scroller.set_shadow_type(Gtk.ShadowType.ETCHED_IN)
        scroller.add(self.tree)

        buttons = Gtk.Box(spacing=6)
        self.add_button_widget = Gtk.Button(label=_('Add'))
        self.add_button_widget.connect('clicked', self.on_add_clicked)
        buttons.pack_start(self.add_button_widget, False, False, 0)
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
        for name in sorted(catalog['models']):
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

    def on_delete_event(self, widget, event):
        self.plugin.model_manager_dialog = None

    def destroy(self):
        self.plugin.model_manager_dialog = None
        Gtk.Dialog.destroy(self)


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
    def __init__(self, plugin, parent, model_name):
        Gtk.Dialog.__init__(
            self,
            title=_('Create Prediction Model “%s”') % model_name,
            transient_for=parent,
            modal=True,
        )
        self.plugin = plugin
        self.model_name = model_name
        self.set_default_size(420, 360)
        self.add_buttons(
            Gtk.STOCK_CANCEL,
            Gtk.ResponseType.CANCEL,
            _('Create'),
            Gtk.ResponseType.OK,
        )
        self.connect('response', self.on_response)
        self.connect('delete-event', self.on_delete_event)

        content = self.get_content_area()
        content.set_border_width(6)

        label = Gtk.Label(label=_('Select saved playlists to analyze.'))
        label.set_xalign(0)
        content.pack_start(label, False, False, 0)

        select_box = Gtk.Box(spacing=6)
        self.select_all_button = Gtk.Button(label=_('Select All'))
        self.select_all_button.connect('clicked', self.on_select_all_clicked)
        select_box.pack_start(self.select_all_button, False, False, 0)
        content.pack_start(select_box, False, False, 4)

        self.store = Gtk.ListStore(bool, str, object)
        self.tree = Gtk.TreeView(model=self.store)
        self.tree.set_headers_visible(True)

        toggle = Gtk.CellRendererToggle()
        toggle.connect('toggled', self.on_playlist_toggled)
        toggle_column = Gtk.TreeViewColumn('', toggle, active=0)
        self.tree.append_column(toggle_column)

        text = Gtk.CellRendererText()
        name_column = Gtk.TreeViewColumn(_('Playlist'), text, text=1)
        name_column.set_expand(True)
        self.tree.append_column(name_column)

        scroller = Gtk.ScrolledWindow()
        scroller.set_policy(Gtk.PolicyType.AUTOMATIC, Gtk.PolicyType.AUTOMATIC)
        scroller.set_shadow_type(Gtk.ShadowType.ETCHED_IN)
        scroller.add(self.tree)
        content.pack_start(scroller, True, True, 6)

        self.status = Gtk.Label()
        self.status.set_xalign(0)
        content.pack_start(self.status, False, False, 0)

        self.populate_playlists()
        self.show_all()

    def populate_playlists(self):
        manager = self.plugin.exaile.playlists
        for name in sorted(manager.list_playlists()):
            self.store.append((False, name, manager.get_playlist(name)))

    def on_playlist_toggled(self, renderer, path):
        self.store[path][0] = not self.store[path][0]

    def on_select_all_clicked(self, button):
        for row in self.store:
            row[0] = True

    def get_selected_playlists(self):
        return [row[2] for row in self.store if row[0]]

    def on_response(self, dialog, response):
        if response == Gtk.ResponseType.OK:
            playlists = self.get_selected_playlists()
            if not playlists:
                self.status.set_text(_('Select at least one playlist.'))
                return

            try:
                trained_model = self.plugin.create_model_from_playlists(
                    self.model_name, playlists
                )
            except Exception as exc:
                dialogs.error(self, _("Could not create suggestions model: %s") % exc)
                return

            dialogs.info(
                self,
                _("Created model from %(playlists)d playlist(s) and %(tracks)d track(s).")
                % {
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


class SuggestionsDialog(Gtk.Dialog):
    def __init__(self, plugin, parent, tracks):
        Gtk.Dialog.__init__(
            self,
            title=_('Suggested Next Tracks'),
            transient_for=parent,
            modal=True,
        )
        self.plugin = plugin
        self.set_default_size(720, 420)
        self.add_buttons(
            Gtk.STOCK_CANCEL,
            Gtk.ResponseType.CANCEL,
            _('Add to Queue'),
            Gtk.ResponseType.OK,
        )
        self.connect('response', self.on_response)
        self.connect('delete-event', self.on_delete_event)

        self.store = Gtk.ListStore(str, str, str, str, object)
        for track in tracks:
            self.store.append(
                (
                    track.get_tag_display('title'),
                    track.get_tag_display('artist'),
                    _display_bpm(track),
                    _display_groups(plugin, track),
                    track,
                )
            )

        self.tree = Gtk.TreeView(model=self.store)
        self.tree.get_selection().set_mode(Gtk.SelectionMode.SINGLE)
        self.tree.get_selection().select_path(0)
        self.tree.connect('row-activated', self.on_row_activated)
        self._add_text_column(_('Title'), 0, True)
        self._add_text_column(_('Artist'), 1, True)
        self._add_text_column(_('BPM'), 2, False)
        self._add_text_column(_('Groups'), 3, True)

        scroller = Gtk.ScrolledWindow()
        scroller.set_policy(Gtk.PolicyType.AUTOMATIC, Gtk.PolicyType.AUTOMATIC)
        scroller.set_shadow_type(Gtk.ShadowType.ETCHED_IN)
        scroller.add(self.tree)

        content = self.get_content_area()
        content.set_border_width(6)
        content.pack_start(scroller, True, True, 0)
        self.show_all()

    def _add_text_column(self, title, column_id, expand):
        renderer = Gtk.CellRendererText()
        renderer.set_property('ellipsize', 3)
        column = Gtk.TreeViewColumn(title, renderer, text=column_id)
        column.set_expand(expand)
        self.tree.append_column(column)

    def get_selected_track(self):
        model, tree_iter = self.tree.get_selection().get_selected()
        if tree_iter is None:
            return None
        return model[tree_iter][4]

    def on_response(self, dialog, response):
        if response == Gtk.ResponseType.OK:
            self.add_selected_track()
        self.destroy()

    def on_row_activated(self, tree, path, column):
        self.tree.get_selection().select_path(path)
        self.add_selected_track()
        self.destroy()

    def add_selected_track(self):
        track = self.get_selected_track()
        if track is not None:
            self.plugin.append_to_queue(track)

    def on_delete_event(self, widget, event):
        self.plugin.suggestion_dialog = None

    def destroy(self):
        self.plugin.suggestion_dialog = None
        Gtk.Dialog.destroy(self)


def _display_bpm(track):
    bpm = track.get_tag_raw('bpm', True)
    return '' if bpm is None else str(bpm)


def _display_groups(plugin, track):
    groups = plugin.get_track_groups(track)
    return ', '.join(sorted(groups))


plugin_class = QueueTrackPredictorPlugin
