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

from gi.repository import GLib
from gi.repository import Gtk

from xl.common import clamp, idle_add

from xlgui.guiutil import GtkTemplate


@GtkTemplate('ui', 'widgets', 'progress.ui')
class ProgressMonitor(Gtk.Box):
    """
    A graphical progress monitor designed to work with
    :class:`xl.common.ProgressThread`
    """

    __gtype_name__ = 'ProgressMonitor'

    label, progressbar = GtkTemplate.Child.widgets(2)

    def __init__(self, manager, thread, description, image=None):
        """
        Initializes the monitor

        :param manager: the parent manager
        :type manager: :class:`ProgressManager`
        :param thread: the thread to run
        :type thread: :class:`xl.common.ProgressThread`
        :param description: the description for this process
        :type description: string
        """
        super(ProgressMonitor, self).__init__()
        self.init_template()

        self.manager = manager
        self.thread = thread
        self._progress_updated = False

        if image is not None:
            self.pack_start(image, False, True, 0)

        self.label.set_text(description)

        self.show_all()
        GLib.timeout_add(100, self.pulsate_progress)

        self.progress_update_id = self.thread.connect(
            'progress-update', self.on_progress_update
        )
        self.done_id = self.thread.connect('done', self.on_done)
        self.thread.start()

    def destroy(self):
        """
        Cleans up
        """

        self._progress_updated = True

        if self.progress_update_id is not None:
            self.thread.disconnect(self.progress_update_id)
            self.thread.disconnect(self.done_id)

            self.progress_update_id = None
            self.done_id = None

    def pulsate_progress(self):
        """
        Pulses the progress indicator until
        the first status update is received
        """
        if self._progress_updated:
            return False

        self.progressbar.pulse()

        return True

    @idle_add()
    def on_progress_update(self, thread, progress):
        """
        Called when the progress has been updated
        """

        if progress is None:
            return

        # Accept a tuple or number between 0 and 100
        if hasattr(progress, '__len__'):
            step, total = progress
            percent = int(((step + 1) / total) * 100)
        else:
            percent = int(progress)

        if percent > 0:
            self._progress_updated = True

        fraction = clamp(percent / 100.0, 0, 1)

        self.progressbar.set_fraction(fraction)
        self.progressbar.set_text('%d%%' % percent)

    @idle_add()
    def on_done(self, thread):
        """
        Called when the thread is finished
        """
        self.manager.remove_monitor(self)

    @GtkTemplate.Callback
    def on_cancel_button_clicked(self, widget):
        """
        Stops the running thread
        """
        self.hide()
        self.thread.stop()
        self.destroy()


class ProgressManager:
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

        :param container: the vertical Gtk.Box that will be holding the
        different progress indicators
        """
        self.box = container

    def add_monitor(self, thread, description, icon_name):
        """
        Adds a progress box

        :param thread: the ProgressThread that should be run once the
            monitor is started
        :param description: a description of the event
        :param icon_name: the name of an icon to display
        """
        image = Gtk.Image.new_from_icon_name(icon_name, Gtk.IconSize.BUTTON)
        monitor = ProgressMonitor(self, thread, description, image)
        self.box.pack_start(monitor, False, True, 0)

        return monitor

    def remove_monitor(self, monitor):
        """
        Removes a monitor from the manager
        """
        monitor.hide()
        monitor.destroy()
