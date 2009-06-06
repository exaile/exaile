# this program is free software; you can redistribute it and/or modify
# it under the terms of the gnu general public license as published by
# the free software foundation; either version 2, or (at your option)
# any later version.
#
# this program is distributed in the hope that it will be useful,
# but without any warranty; without even the implied warranty of
# merchantability or fitness for a particular purpose.  see the
# gnu general public license for more details.
#
# you should have received a copy of the gnu general public license
# along with this program; if not, write to the free software
# foundation, inc., 675 mass ave, cambridge, ma 02139, usa.

from xlgui import guiutil
from xl import event
import gtk, threading

class ProgressMonitor(gtk.Frame):
    """
        A progress monitor
    """
    def __init__(self, manager, thread, desc, icon):
        """
            Initializes the monitor
        """
        gtk.Frame.__init__(self)
        self.manager = manager
        self.thread = thread
        self.desc = desc
        self.icon = icon
       
        self._setup_widgets()
        self.show_all()

        event.add_callback(self.progress_update, 'progress_update', thread)
        thread.start()

    @guiutil.gtkrun
    def progress_update(self, type, thread, percent):
        """
            Called when the progress has been updated
        """
        self.progress.set_fraction(float(percent) / 100)
        self.progress.set_text('%d%%' % percent)
        if percent == 100 or percent == 'complete':
            if hasattr(self.thread, 'thread_complete'):
                self.thread.thread_complete()
            self.stop_monitor()

    def stop_monitor(self, *e):
        """
            Stops this monitor, removes it from the progress area
        """
        self.thread.stop_thread()
        self.manager.remove_monitor(self)

    def _setup_widgets(self):
        """
            Sets up the various widgets for this object
        """
        self.set_shadow_type(gtk.SHADOW_NONE)
        desc = self.desc
        icon = self.icon

        box = gtk.VBox()
        box.set_border_width(3)
        label = gtk.Label(desc)
        label.set_use_markup(True)
        label.set_alignment(0, 0.5)
        label.set_padding(3, 0)

        box.pack_start(label, False, False)

        pbox = gtk.HBox()
        pbox.set_spacing(3)

        img = gtk.Image()
        img.set_from_stock(icon, gtk.ICON_SIZE_SMALL_TOOLBAR)
        img.set_size_request(32, 32)
        pbox.pack_start(img, False, False)
       
        ibox = gtk.VBox()
        l = gtk.Label()
        l.set_size_request(2, 2)
        ibox.pack_start(l, False, False)
        self.progress = gtk.ProgressBar()
        self.progress.set_text(' ')
        
        ibox.pack_start(self.progress, True, False)
        l = gtk.Label()
        l.set_size_request(2, 2)
        ibox.pack_start(l, False, False)
        pbox.pack_start(ibox, True, True)

        button = gtk.Button()
        img = gtk.Image()
        img.set_from_stock('gtk-stop', gtk.ICON_SIZE_SMALL_TOOLBAR)
        button.set_image(img)

        pbox.pack_start(button, False, False)
        button.connect('clicked', self.stop_monitor)

        box.pack_start(pbox, True, True)
        self.add(box)

class ProgressManager(object):
    """
        Manages the [possibly multiple] progress bars that will allow the user
        to interact with different long running tasks that may occur in the
        application.  

        The user should be able to see what task is running, the description,
        the current progress, and also be able to stop the task if they wish.
    """
    def __init__(self, container):
        """
            Initializes the manager

            @param container: the gtk.VBox that will be holding the different
            progress indicators
        """
        self.box = container

    def add_monitor(self, thread, description, stock_icon):
        """
            Adds a progress box

            @param thread: the ProgressThread that should be run once the
                monitor is started
            @param description: a description of the event
            @param stock_icon: the icon to display
        """
        monitor = ProgressMonitor(self, thread, description, stock_icon)
        self.box.pack_start(monitor, False, False)
        return monitor

    def remove_monitor(self, monitor):
        """
            Removes a monitor from the manager
        """
        self.box.remove(monitor)
        monitor.hide()
