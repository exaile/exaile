# -*- coding: utf-8 -*-
"""
Copyright (c) 2019 Fernando Póvoa (sbrubes)

Permission is hereby granted, free of charge, to any person obtaining a copy
of this software and associated documentation files (the "Software"), to deal
in the Software without restriction, including without limitation the rights
to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
copies of the Software, and to permit persons to whom the Software is
furnished to do so, subject to the following conditions:

The above copyright notice and this permission notice shall be included in all
copies or substantial portions of the Software.

THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
SOFTWARE.
"""
import itertools
import threading
import timeit

from gi.repository import GLib
from gi.repository import Gtk

import xl

from xl.nls import gettext as _

import _model

from _base import SETTINGS, Logger, create_event
from _database import CantSelectException, execute_select
from _pattern import CONST_FIELDS
from _utils import ADDITIONAL_FILTER_NONE_VALUE, get_error_icon, represent_length_as_str, represent_timestamp_as_str

# Logger
_LOGGER = Logger(__name__)

_APPEND_ROW_EVENT = create_event('append-row')
_LOAD_END_EVENT = create_event('load-end')

_LOADING_MSG = _('loading...')

_id_count = itertools.count()

_loading_ids = {}
_loading_ids_lock = threading.Lock()


@xl.common.threaded
def _process_select(loading_id, model, parent, place_holder,
                    select_params, subgroup):
    """
        Process a selection (tree view item load)
        :param loading_id: the id to load
        :param model: Gtk.ListStore
        :param parent: Gtk.TreeIter or None
        :param place_holder: Gtk.TreeIter with the loading msg
        :param select_params: parameters used to filter selection
        :param subgroup: the PatternView Subgroup
        :return: None
    """
    append_row_event = _APPEND_ROW_EVENT
    initial_timer = timeit.default_timer()
    info_msg = '%sed loading (%d)'
    last_group = ''
    separator_index = (1 if subgroup.is_root and
                            SETTINGS['draw_separators']
                       else 0)
    items_count = 0
    _LOGGER.debug(info_msg, 'start', loading_id)
    ex = None
    icons = subgroup.icons
    outputs = subgroup.outputs
    try:
        rows = execute_select(*select_params)
    except CantSelectException as e:
        ex = e
    else:
        item_format = dict(length=represent_length_as_str,
                           added=represent_timestamp_as_str,
                           mtime=represent_timestamp_as_str)
        for row in rows:
            items_count += 1
            if separator_index and row[0] != last_group:
                last_group = row[0]
                append_row_event.log(None, (model, parent, {}, True))

            field_values = row[separator_index:-len(CONST_FIELDS)]
            item_data = {
                field: (
                    GLib.markup_escape_text(value).decode(encoding='utf-8')
                        if isinstance(value, basestring) else
                    (item_format.get(field, lambda x: x)(value))
                ) for field, value in zip(subgroup.fields, field_values)
            }

            item_data.update({
                val: item_format.get(val, lambda x: x)(row[-len(CONST_FIELDS) + idx])
                    for idx, val in enumerate(CONST_FIELDS)
            })

            append_row_event.log(
                None,
                (model, parent,
                 {"Icon": icons['tree_view'],
                  "Title": outputs['tree_view'].format(item_data),
                  "ValueArray": field_values,
                  "ValueDict": item_data,
                  "TooltipIcon": icons['tooltip'],
                  "TooltipText": outputs['tooltip'].format(item_data)},
                 subgroup.is_bottom)
            )

    def post_remove():
        """
            Post remove, pop's loading_id and notify_end
            :return: None
        """
        with _loading_ids_lock:
            notify_end_list = _loading_ids.pop(loading_id)
            for notify_end in notify_end_list:
                if notify_end:
                    notify_end.set()

    _LOAD_END_EVENT.log(
        None, (model, place_holder, post_remove, ex)
    )

    _LOGGER.debug(
        info_msg + ': %.3f secs, %d items', 'end', loading_id,
        timeit.default_timer() - initial_timer, items_count
    )


def _add_place_holder(model, parent):
    """
        Adds a place holder (loading msg item)
        :param model: Gtk.ListStore
        :param parent: Gtk.TreeIter or None
        :return: Gtk.TreeIter
    """
    return model.append(
        parent,
        _model.row({
            'Title': _LOADING_MSG,
            'TooltipText': _LOADING_MSG,
            'ValueArray': '',
            'Id': -1
        })
    )


def _get_id():
    """
        Get an id (unique)
        :return: int
    """
    return _id_count.next()

def _on_append_row(_evt_name, _obj, data):
    """
        Handles _APPEND_ROW_EVENT
        :param _evt_name:
        :param _obj:
        :param data: (model, parent, row, is_bottom)
        :return: None
    """
    model, parent, row_dict, is_bottom = data
    row_dict["Id"] = _get_id()
    added = model.append(parent, _model.row(row_dict))
    if not is_bottom and not row_dict["ValueArray"] is None:
        _add_place_holder(model, parent=added)


def _on_load_end(_evt_name, _obj, data):
    """
        Handles _LOAD_END_EVENT
        :param _evt_name:
        :param _obj:
        :param data: (model, it, post_action, ex)
        :return: None
    """
    model, it, post_action, ex = data
    error_msg = ''
    if ex:
        error_msg = _('error loading') + (' (%s)' % ex.message)
    elif model.iter_n_children(model.iter_parent(it)) == 1:
        error_msg = _('no items')

    if error_msg:
        for i in ["Icon", "TooltipIcon"]:
            model.set_value(it, _model.index(i), get_error_icon(Gtk.IconSize.SMALL_TOOLBAR))

        for i in ["Title", "TooltipText"]:
            model.set_value(it, _model.index(i), '<b>' + error_msg + '</b>')
    else:
        model.remove(it)

    post_action()


def load(model, view_pattern, parent, notify_end=None,
         additional_filter=ADDITIONAL_FILTER_NONE_VALUE):
    """
        Loads an item
        :param model: Gtk.ListStore
        :param view_pattern: _pattern.ViewPattern
        :param parent: Gtk.TreeIter or None
        :param notify_end: threading.Event
        :param additional_filter: additional filter
        :return: None
    """
    if parent is None:
        depth = 0
        place_holder = _add_place_holder(model, None)
        loading_id = _get_id()
    else:
        depth = model.iter_depth(parent) + 1
        place_holder = model.iter_children(parent)
        if place_holder is None or \
                _model.get_value_array(model, place_holder) != '':
            if notify_end:
                notify_end.set()
            return  # already loaded or bottom

        loading_id = model.get_value(parent, _model.index("Id"))

    with _loading_ids_lock:
        if loading_id in _loading_ids:
            if notify_end:
                _loading_ids[loading_id].append(notify_end)
            return  # already loading
        else:
            _loading_ids[loading_id] = [notify_end]

    subgroup = view_pattern[depth]
    parent_values = _model.get_parent_values(model, parent)
    select_params = (
        subgroup.get_select(parent_values, additional_filter[0]),
        filter(lambda x: x is not None, parent_values + additional_filter[1])
    )

    _process_select(
        loading_id, model, parent,
        place_holder, select_params, subgroup
    )


_APPEND_ROW_EVENT.connect(_on_append_row)
_LOAD_END_EVENT.connect(_on_load_end)
