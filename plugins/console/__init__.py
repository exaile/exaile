import sys, traceback, gtk, gobject
from cStringIO import StringIO
from xl.nls import gettext as _
from xlgui import guiutil
from xl import event

class PyConsole(gtk.Window):
    def __init__(self, dict):
        gtk.Window.__init__(self)
        self.dict = dict

        self.buffer = StringIO()

        self.set_title(_("Python Console - Exaile"))
        self.set_border_width(12)
        self.set_default_size(450, 250)

        vbox = gtk.VBox(False, 12)
        self.add(vbox)

        sw = gtk.ScrolledWindow()
        vbox.pack_start(sw)
        sw.set_shadow_type(gtk.SHADOW_IN)
        sw.set_policy(gtk.POLICY_NEVER, gtk.POLICY_ALWAYS) 
        self.text_view = tv = gtk.TextView()
        sw.add(tv)
        tv.set_editable(False)
        self.text_buffer = buff = tv.get_buffer()
        self.end_mark = buff.create_mark(None, buff.get_end_iter(), False)
        tv.set_wrap_mode(gtk.WRAP_WORD)

        hbox = gtk.HBox(False, 6)
        vbox.pack_start(hbox, False)
        label = gtk.Label('>>>')
        hbox.pack_start(label, False)
        self.entry = entry = gtk.Entry()
        hbox.pack_start(entry)
        entry.connect('activate', self.entry_activated)

        entry.grab_focus()
        vbox.show_all()

    def entry_activated(self, entry, user_data=None):
        """
            Called when the user presses Return on the GtkEntry.
        """
        self.execute(entry.get_text())
        entry.select_region(0, -1)

    def execute(self, code):
        """
            Executes some Python code.
        """
        stdout = sys.stdout
        try:
            pycode = compile(code, '<console>', 'single')
            sys.stdout = self.buffer
            exec pycode in self.dict
        except:
            sys.stdout = stdout
            exc = traceback.format_exception(*sys.exc_info())
            del exc[1] # Remove our function.
            result = ''.join(exc)
        else:
            sys.stdout = stdout
            result = self.buffer.getvalue()
            # Can't simply close and recreate later because help() stores and
            # reuses stdout.
            self.buffer.truncate(0) 
        result = '>>> %s\n%s' % (code, result)
        self.text_buffer.insert(self.text_buffer.get_end_iter(), result)
        # Can't use iter, won't scroll correctly.
        self.text_view.scroll_to_mark(self.end_mark, 0)
        self.entry.grab_focus()

PLUGIN = None
def _enable(exaile):
    global PLUGIN
    PLUGIN = PyConsole({'exaile': exaile})
    PLUGIN.connect('destroy', console_destroyed)
    PLUGIN.present()

def enable(exaile):
    def enb(eventname, exaile, nothing):
        gobject.idle_add(_enable, exaile)

    if exaile.loading:
        event.add_callback(enb, "exaile_loaded")
    else:
        enb(None, exaile, None)

def console_destroyed(*args):
    global PLUGIN
    PLUGIN = None

def disable(exaile):
    global PLUGIN
    if PLUGIN:
        PLUGIN.destroy()
        PLUGIN = None
