#
# Copyright (C) 2015 Dustin Spicuzza <dustin@virtualroadside.com>
#
# This library is free software; you can redistribute it and/or
# modify it under the terms of the GNU Lesser General Public
# License as published by the Free Software Foundation; either
# version 2.1 of the License, or (at your option) any later version.
#
# This library is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the GNU
# Lesser General Public License for more details.
#
# You should have received a copy of the GNU Lesser General Public
# License along with this library; if not, write to the Free Software
# Foundation, Inc., 51 Franklin St, Fifth Floor, Boston, MA  02110-1301
# USA

from os.path import abspath, join

import inspect
import warnings

from gi.repository import GLib
from gi.repository import GObject
from gi.repository import Gtk

__all__ = ['GtkTemplate', 'GtkChild', 'GtkCallback']


def _connect_func(builder, obj, signal_name, handler_name,
                  connect_object, flags, cls):
    '''Handles GtkBuilder signal connect events'''
    
    # Deal with signals on the template object itself
    if connect_object is None:
        if not isinstance(obj, cls):
            warnings.warn("Cannot determine object to connect '%s' to" %
                          handler_name)
            return
        
        connect_object = obj
    elif not isinstance(connect_object, cls):
        warnings.warn("Handler '%s' user_data is not set to an instance of '%s'" %
                      (handler_name, cls))
        return
    
    if handler_name not in connect_object.__gtemplate_methods__:
        errmsg = "@GtkCallback handler '%s' was not found for signal '%s'" % \
                 (handler_name, signal_name)
        warnings.warn(errmsg)
        return
    
    handler = getattr(connect_object, handler_name)

    if flags == GObject.ConnectFlags.AFTER:
        obj.connect_after(signal_name, handler)
    else:
        obj.connect(signal_name, handler)
    
    connect_object.__connected_template_signals__.add(handler_name)


def _register_template(cls, ui_path):
    '''Registers the template for the widget and hooks init_template'''
    
    with open(ui_path, 'rb') as fp:
        cls.set_template(GLib.Bytes.new(fp.read()))
    
    bound_methods = set()
    bound_widgets = set()
    
    # Walk the class, find callback objects
    for name in dir(cls):
        
        o = getattr(cls, name, None)
        
        if inspect.ismethod(o):
            if hasattr(o, '_gtk_callback'):
                bound_methods.add(name)
                # Don't need to call this, as connect_func always gets called
                #cls.bind_template_callback_full(name, o)
        elif isinstance(o, _GtkChild):
            cls.bind_template_child_full(name, True, 0)
            bound_widgets.add(name)
    
    # Have to setup a special connect function to connect at template init
    # because the methods are not bound yet
    cls.set_connect_func(_connect_func, cls)
    
    # This might allow nested composites.. haven't tested it
    bound_methods.update(getattr(cls, '__gtemplate_methods__', set()))
    cls.__gtemplate_methods__ = bound_methods
    
    bound_widgets.update(getattr(cls, '__gtemplate_widgets__', set()))
    cls.__gtemplate_widgets__ = bound_widgets
    
    base_init_template = cls.init_template
    cls.init_template = lambda s: _init_template(s, cls, base_init_template)
    

def _init_template(self, cls, base_init_template):
    '''This would be better as an override for Gtk.Widget'''
    
    connected_signals = set()
    self.__connected_template_signals__ = connected_signals
    
    base_init_template(self)
    
    for name in self.__gtemplate_widgets__:
        widget = self.get_template_child(cls, name)
        self.__dict__[name] = widget
        
        if widget is None:
            # Bug: if you bind a template child, and one of them was
            #      not present, then the whole template is broken (and
            #      it's not currently possible for us to know which 
            #      one is broken either -- but the stderr should show
            #      something useful with a Gtk-CRITICAL message)
            raise AttributeError("A missing child widget was set using " +
                                 "GtkChild and the entire template is now " +
                                 "broken (widgets: %s)" %
                                 ', '.join(self.__gtemplate_widgets__))
    
    for name in self.__gtemplate_methods__.difference(connected_signals):
        errmsg = ("Signal '%s' was declared with @GtkCallback " +
                  "but was not present in template") % name
        warnings.warn(errmsg)

class _GtkTemplate(object):
    '''
        Use this class decorator to signify that a class is a composite
        widget which will receive widgets and connect to signals as
        defined in a UI template. You must call init_template to
        cause the widgets/signals to be initialized from the template::
        
            @GtkTemplate(ui='foo.ui')
            class Foo(Gtk.Box):
                
                def __init__(self):
                    super(Foo, self).__init__()
                    self.init_template()
    
        Note: This is implemented as a class decorator, but if it were
        included with PyGI I suspect it might be better to do this
        in the GObject metaclass (or similar) so that init_template
        can be called automatically instead of forcing the user to do it.
    '''
    
    __ui_path__ = None
    
    @staticmethod
    def set_ui_path(*path):
        '''
            Call this *before* loading anything that uses GtkTemplate,
            or it will fail to load your template file
            
            :param path: one or more path elements, will be joined together
                         to create the final path
            
            TODO: Alternatively, could wait until first class instantiation
                  before registering templates? Would need a metaclass...
        '''
        _GtkTemplate.__ui_path__ = abspath(join(*path))
    
    
    def __init__(self, ui):
        if isinstance(ui, (list, tuple)):
            ui = join(ui)
        if self.__ui_path__ is not None:
            self.ui = join(_GtkTemplate.__ui_path__, ui)
        else:
            self.ui = ui
    
    def __call__(self, cls):
        _register_template(cls, self.ui)
        return cls


def _GtkCallback(f):
    '''Marks a method as a callback method to be attached to a signal'''
    f._gtk_callback = True
    return f

# TODO: Make it easier for IDE to introspect this
class _GtkChild(object):
    '''
        Assign this to an attribute in your class definition and it will
        be replaced with a widget defined in the UI file when init_template
        is called
    '''
    
    __slots__ = []
    
    @staticmethod
    def widgets(count):
        '''Allows silliness like foo,bar = GtkChild()'''
        return [_GtkChild() for _ in xrange(count)]

    
# Future shim support if this makes it into PyGI
if hasattr(Gtk, 'GtkChild'):
    GtkChild = Gtk.GtkChild
    GtkCallback = Gtk.GtkCallback
    GtkTemplate = lambda c: c
else:
    GtkChild = _GtkChild
    GtkCallback = _GtkCallback
    GtkTemplate = _GtkTemplate
    
