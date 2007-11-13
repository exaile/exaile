# Copyright (C) 2006 Adam Olsen
# Copyright (C) 2007 Johannes Sasongko <sasongko@gmail.com>
#
# This program is free software; you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation; either version 2 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License along
# with this program; if not, write to the Free Software Foundation, Inc.,
# 51 Franklin Street, Fifth Floor, Boston, MA 02110-1301 USA.

import sys, time, traceback

# Copied from common because common requires gtk.
def to_unicode(x, default_encoding=None):
    if isinstance(x, unicode):
        return x
    elif default_encoding and isinstance(x, str):
        # This unicode constructor only accepts "string or buffer".
        return unicode(x, default_encoding)
    else:
        return unicode(x)

def log(message, multi=False):
    """Log a single-line message."""
    try:
        message = to_unicode(message)
    except UnicodeDecodeError:
        log_stack("Can't decode: " + `message`)
        # Fall through.
    _log(message)

def log_multi(lines):
    """Log a multiline message."""
    for i, line in enumerate(lines):
        try:
            lines[i] = to_unicode(line)
        except UnicodeDecodeError:
            log_stack("Can't decode: " + `line`)
            # Fall through,
    _log(lines, multi=True)

def log_exception():
    """Log current exception."""
    message = file_and_line()
    message.extend(traceback.format_exc().split('\n'))
    _log(message, multi=True)

def log_stack(description=None, skip=1):
    """Log current stack."""
    message = file_and_line(skip)
    message.append('Stack:')
    stack = traceback.format_stack()
    for i in xrange(0, len(stack) - skip):
        message.append(stack[i].rstrip())
    if description:
        try:
            description = to_unicode(description)
        except UnicodeDecodeError:
            log_stack("Can't decode: " + `description`)
            # Fall through.
        message.append(description)
    _log(message, multi=True)

def file_and_line(skip=1):
    """Return a nicely formatted string containing current file and function."""
    co = sys._getframe(skip + 1).f_code
    return ["-----------------------",
            " %s ( %s @ %s):" % (co.co_name, co.co_filename, co.co_firstlineno),
            "-----------------------"]


# Light (console-only) logging.

queue = []

# Will be replaced by the heavy logger when it's initialized.
def _log(message, multi=False):
    timestamp = time.time()
    if multi:
        for line in message:
            console_log(line)
            queue.append((line, timestamp))
    else:
        console_log(message)
        queue.append((message, timestamp))

def console_log(message):
    try:
        print message
    except UnicodeEncodeError: # Can't encode to system encoding.
        print `message`


# Heavy logging.

gobject = None
gui = None

def init(exaile, filename):
    def inject_heavy_logging():
        global _log, gui, queue
        gui = LoggerGUI(exaile, filename)
        for message, timestamp in queue:
            gui.log(message, timestamp)
        _log = _heavy_log
        del queue
    global gobject
    import gobject
    gobject.idle_add(inject_heavy_logging)

def _heavy_log(message, multi=False):
    gobject.idle_add(_real_heavy_log, message, time.time(), multi)

def _real_heavy_log(message, timestamp, multi=False):
    if multi:
        for line in message:
            console_log(line)
            gui.log(line, timestamp)
    else:
        console_log(message)
        gui.log(message, timestamp)

class LoggerGUI:
    def __init__(self, exaile, filename):
        import gtk.glade
        self.exaile = exaile
        self.filename = filename
        xml = gtk.glade.XML('exaile.glade', 'DebugDialog', 'exaile')
        self.dialog = xml.get_widget('DebugDialog')
        self.dialog.set_transient_for(self.exaile.window)
        self.view = xml.get_widget('debug_textview')
        self.buf = buf = self.view.get_buffer()
        self.end_mark = buf.create_mark(None, buf.get_end_iter(), False)
        self.log_file = None
        xml.get_widget('debug_ok_button').connect('clicked', 
            lambda *e: self.dialog.hide())
        self.dialog.connect('delete_event', self._closed)

    def _closed(self, *e):
        self.dialog.hide()
        return True

    def __del__(self):
        if self.log_file:
            self.log_file.close()

    def log(self, message, timestamp=None):
        if not timestamp: timestamp = time.time()
        lt = time.localtime(timestamp)
        text = "[%s] %s\n" % (time.strftime("%H:%M:%S", lt), message)

        self.buf.insert(self.buf.get_end_iter(), text)

        if not self.log_file:
            try:
                self.log_file = open(self.filename, 'a')
            except:
                self.log_file = None

        if self.log_file:
            self.log_file.write(text)
            self.log_file.flush()

        self.view.scroll_to_mark(self.end_mark, 0)
