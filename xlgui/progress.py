# Copyright (C) 2008-2010 Adam Olsen
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
# Foundation, Inc., 675 Mass Ave, Cambridge, MA 02139, USA.
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

import gobject
import gtk

from xl import xdg
from xlgui import commondialogs, icons
from xlgui.commondialogs import MessageBar

class ProgressMonitor(MessageBar):
    """
        A graphical progress monitor
    """
    def __init__(self, manager, thread, description):
        """
            Initializes the monitor

            :param manager: the parent manager
            :type manager: :class:`ProgressManager`
            :param thread: the thread to run
            :type thread: :class:`threading.Thread`
            :param description: the description for this process
            :type description: string
        """
        MessageBar.__init__(self, buttons=gtk.BUTTONS_CANCEL,
            text=description)
        self.set_no_show_all(False)

        self.manager = manager
        self.thread = thread

        self.progressbar = gtk.ProgressBar()
        self.progressbar.pulse()
        self.get_message_area().pack_start(self.progressbar, False)

        self.show_all()

        self.connect('response', self.on_response)
        self.timeout_id = gobject.timeout_add(100, self.on_timeout)
        self.progress_update_id = self.thread.connect('progress-update',
            self.on_progress_update)
        self.done_id = self.thread.connect('done', self.on_done)
        self.thread.start()

    def destroy(self):
        """
            Cleans up
        """
        if self.timeout_id is not None:
            gobject.source_remove(self.timeout_id)

        self.thread.disconnect(self.progress_update_id)
        self.thread.disconnect(self.done_id)

        MessageBar.destroy(self)

    def on_timeout(self):
        """
            Pulses the progress indicator until
            the first status update is received
        """
        self.progressbar.pulse()

        return True

    def on_progress_update(self, thread, percent):
        """
            Called when the progress has been updated
        """
        if self.timeout_id is not None:
            gobject.source_remove(self.timeout_id)
            self.timeout_id = None

        fraction = float(percent) / 100

        fraction = max(0, fraction)
        fraction = min(fraction, 1.0)

        self.progressbar.set_fraction(fraction)
        self.progressbar.set_text('%d%%' % percent)

    def on_done(self, thread):
        """
            Called when the thread is finished
        """
        self.manager.remove_monitor(self)

    def on_response(self, widget, response):
        """
            Stops the running thread
        """
        if response == gtk.RESPONSE_CANCEL:
            widget.hide()
            widget.destroy()
            self.thread.stop()

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

            :param container: the gtk.VBox that will be holding the different
            progress indicators
        """
        self.box = container

    def add_monitor(self, thread, description, stock_id):
        """
            Adds a progress box

            :param thread: the ProgressThread that should be run once the
                monitor is started
            :param description: a description of the event
            :param stock_id: the stock id of an icon to display
        """
        monitor = ProgressMonitor(self, thread, description)
        image = gtk.image_new_from_stock(stock_id, gtk.ICON_SIZE_DIALOG)
        monitor.set_image(image)
        self.box.pack_start(monitor)

        return monitor

    def remove_monitor(self, monitor):
        """
            Removes a monitor from the manager
        """
        monitor.hide()
        monitor.destroy()

