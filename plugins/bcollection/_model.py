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
from gi.repository import GdkPixbuf
from gi.repository import Gtk

#: dict: Fields to model
_FIELDS = {
    "Icon":         (0, GdkPixbuf.Pixbuf),
    "Title":        (1, str),
    "ValueArray":   (2, object),
    "ValueDict":    (3, object),
    "TooltipIcon":  (4, GdkPixbuf.Pixbuf),
    "TooltipText":  (5, str),
    "Id":           (6, int)
}


def indexed():
    """
        Gets indexed model fields
        :return: list - index ordered list of fields from model
    """
    return sorted(
        _FIELDS.items(),
        key=lambda x: x[1][0] if x[1][0] >= 0 else (len(_FIELDS) - 1) + (x[1][0] * -1)
    )


def new():
    """
        Creates a new model
        :return: Gtk.TreeStore
    """
    return Gtk.TreeStore(*(i[1][1] for i in indexed()))


def index(name):
    """
        Get the index related to a field name
        :param name: str
        :return: int
    """
    return _FIELDS[name][0]


def get_value_array(model, it):
    """
        Get the 'ValueArray' value
        :param model: Gtk.TreeModel
        :param it: Gtk.TreeIter
        :return: list
    """
    return model.get_value(it, index("ValueArray"))


def get_value_dict(model, it):
    """
        Get the 'ValueDict' value
        :param model: Gtk.TreeModel
        :param it: Gtk.TreeIter
        :return: dict
    """
    return model.get_value(it, index("ValueDict"))


def row(d):
    """
        From a dict to row
        :param d: dict
        :return: list
    """
    def columns():
        """
            Based on index, yield columns
            :return: yield value or None
        """
        for i in indexed():
            try:
                yield d[i[0]]
            except KeyError:
                yield None

    return list(columns())


def row_separator_func(model, it, _d):
    """
        Gtk.TreeViewRowSeparatorFunc
        :param model: Gtk.TreeModel
        :param it: Gtk.TreeIter
        :param _d: object or None
        :return: value array or None
    """
    return (get_value_array(model, it) is None)


def get_each_child(model, it):
    """
        Each child from model
        :param model: Gtk.TreeModel
        :param it: Gtk.TreeIter or None
        :return: yield parents
    """
    n = 0
    child_it = model.iter_nth_child(it, n)
    while child_it:
        yield child_it

        n += 1
        child_it = model.iter_nth_child(it, n)


def get_child(model, it):
    """
        Get last child nodes
        :param model: Gtk.TreeModel
        :param it: Gtk.TreeIter or None
        :return: yield child
    """
    if model.iter_has_child(it):
        for i in get_each_child(model, it):
            for child in get_child(model, i):
                yield child
    else:
        yield it


def get_each_parent(model, it):
    """
        Each parent from model
        :param model: Gtk.TreeModel
        :param it: Gtk.TreeIter or None
        :return: yield parents (from parent to childs)
    """
    if it:
        for i in get_each_parent(model, model.iter_parent(it)):
            yield i

        yield it


def get_parent_values(model, parent):
    """
        Get parent values from model
        :param model: Gtk.ListStore
        :param parent: Gtk.TreeIter
        :return: list of values
    """
    values = []
    for i in get_each_parent(model, parent):
        values += get_value_array(model, i)
    return values
