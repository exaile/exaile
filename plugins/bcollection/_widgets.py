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
from gi.repository import Gdk

from _utils import create_with


def connect(gtk_widget, events, fnc):
    """
        Connect events to function
        :param gtk_widget: Gtk.Widget
        :param events: list of str
        :param fnc: function to connect
        :return: None
    """
    for i in events:
        Widgets.Event(gtk_widget, i, fnc)


def _all(model):
    """
        All widgets
        :param model: widget model
        :return: list
    """
    res = []

    def get(item):
        """
            Append item to result
            :param item:
            :return: False
        """
        res.append(item)
        return False

    _filter(get, model)

    return res


def _filter(fnc, model):
    """
        Filter widget model with first param
        :param fnc: function (x) - return True to stop
        :param model: widget model
        :return: Widgets.Item or None
    """
    if isinstance(model, (list, tuple)):
        for i in model:
            ret = _filter(fnc, i)
            if ret:
                return ret

        return None
    elif isinstance(model, Widgets.Item):
        if fnc(model):
            return model
        else:
            return _filter(fnc, model.child)


def _focus(item):
    """
        Focus item
        :param item: Widgets.Item
        :return: bool
    """
    if isinstance(item, Widgets.Item):
        if item.get_can_focus():
            item.grab_focus()
            return True
        else:
            return _focus(item.child)
    elif isinstance(item, (list, tuple)):
        for i in item:
            res = _focus(i)
            if res:
                return True

        return False
    else:
        return False


def _parse(parent, model, builder):
    """
        Parse widgets model
        :param parent: Widgets.Item
        :param model: widget model
        :param builder: Gtk.Builder
        :return: [] or list or Widgets.Item
    """
    if model is None:
        return []
    elif isinstance(model, dict):
        return [Widgets.Item(k, parent, builder, v) for k, v in model.items()]
    elif isinstance(model, (list, tuple)):
        return [_parse(parent, i, builder) for i in model]
    elif isinstance(model, basestring):
        return Widgets.Item(model, parent, builder, None)
    else:
        return None


class Widgets:
    """
        Class helper to deal with Widgets
    """

    class Event:
        """
            Class to handle a event to widget (Gtk)
        """

        def __init__(self, widget, name, func, *params):
            """
                Constructor
                Already connects event
                :param widget: Gtk.Widget
                :param name: str - event name
                :param func: function to connect
                :param params: *params
            """
            self.widget = widget
            self.name = name
            self.func = func
            self.params = params
            self.handler_id = None

            events = getattr(widget, 'events', {})
            events[name] = self
            setattr(widget, 'events', events)

            self.connect()

        def connect(self):
            """
                Connect event
                Disconnect first (if connected)
                :return: None
            """
            self.disconnect()
            self.handler_id = self.widget.connect(self.name, self.func, *self.params)

        def disconnect(self):
            """
                Disconnect event
                :return: None
            """
            if self.handler_id is not None:
                self.widget.disconnect(self.handler_id)
                self.handler_id = None

        @property
        def suspended(self):
            """
                Gets a with statement that disconnects and reconnects event
                :return: _utils.WithClass
            """
            return create_with(self.disconnect, self.connect)

    class Item:
        """
            Widget item
        """

        def __init__(self, name, parent, builder, model):
            """
                Constructor
                :param name: str
                :param parent: Widgets.Item
                :param builder: Gtk.Builder
                :param model: Gtk.TreeModel
            """
            self.name = name
            self.parent = parent
            self.gtk_object = builder.get_object(name)
            self.child = _parse(self, model, builder)
            self.model = model

        def __getattr__(self, item):
            """
                Get attr
                :param item: str
                :return: encapsulated call or attribute from Gtk.Widget
            """
            gtk_object_attr = getattr(self.gtk_object, item)

            def encapsulate_call(*args, **kwargs):
                def get_val(i):
                    val = getattr(i, "gtk_object", None)
                    return i if val is None else val

                new_args = [get_val(i) for i in args]
                new_kwargs = {k: get_val(v) for k, v in kwargs.items()}
                return gtk_object_attr(*new_args, **new_kwargs)

            return encapsulate_call if callable(gtk_object_attr) else gtk_object_attr

        def __repr__(self):
            """
                Name
                :return: str - name
            """
            return self.name

        def visible(self):
            """
                Set it visible
                :return: None
            """
            self.parent.gtk_object.set_visible_child(self.gtk_object)

        def focus(self):
            """
                Get focus
                :return: bool
            """
            return _focus(self)

        def on_key_press_event(self, _gtk_widget, evt):
            """
                On key press event
                :param _gtk_widget: Gtk.Widget
                :param evt: Gdk.EventKey
                :return: bool
            """
            if evt.keyval in (Gdk.KEY_Tab, Gdk.KEY_ISO_Left_Tab):
                all_child = _all(self.parent.child)
                index = (
                    all_child.index(self)
                    + (-1 if evt.state & Gdk.ModifierType.SHIFT_MASK else 1)
                ) % len(all_child)
                return all_child[index].focus()

            return False

    def __init__(self, builder, widgets_model, **kwargs):
        """
            Constructor
            :param builder: Gtk.Builder
            :param widgets_model: list
            :param kwargs: events
        """
        model = _parse(None, widgets_model, builder)

        self.__widgets = widgets = {}

        def catalog(i):
            """
                Catalog item
                :param i: Widgets.Item
                :return: False
            """
            widgets[i.name] = i
            return False

        _filter(catalog, model)

        events = dict(
            _button=['activate', 'clicked'],
            _switch=['state-set'],
            combo_box=['changed'],
            search_entry=['activate'],
        )

        for i in widgets:
            if i in kwargs:
                for j, evt in events.items():
                    if i.endswith(j):
                        item = self[i]
                        connect(item, ['key-press-event'], item.on_key_press_event)
                        connect(item, evt, kwargs[i])
                        break

    @property
    def all(self):
        """
            All widgets
            :yield: Widgets.Item
        """
        for i in _all(self.__widgets):
            yield i

    def __getitem__(self, item):
        """
            Get widget
            :param item: str
            :return: GObject.Object
        """
        return self.__widgets[item]

    def __setitem__(self, key, value):
        """
            Set item
            :param key: str
            :param value: GObject.Object
            :return: None
        """
        self.__widgets[key].gtk_object = value
