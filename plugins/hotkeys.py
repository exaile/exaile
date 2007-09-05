import gtk, gconf, gobject
import xl.plugins as plugins
from gettext import gettext as _

PLUGIN_NAME = _("Global Hotkeys")
PLUGIN_AUTHORS = ['Sayamindu Dasgupta <sayamindu@gnome.org>',
                  'Lincoln de Sousa <lincoln@archlinux-br.org']
PLUGIN_VERSION = '0.6.2'
PLUGIN_DESCRIPTION = _(r"""Enables support for Global Hotkeys in metacity
(default gnome window manager)""")
PLUGIN_ENABLED = False

b = gtk.Button()
PLUGIN_ICON = b.render_icon(gtk.STOCK_MEDIA_PLAY, gtk.ICON_SIZE_MENU)
b.destroy()

###
# Add keyboard shortcut items here in tuples in the following format:
#
#    setting name   shortcut    command         label
##
items = (
    ('show_hide',   '<Super>p', 'exaile',      _('Show/Hide Exaile:')),
    ('play',        '<Super>x', 'exaile -a',   _('Play:')),
    ('play_pause',  '<Super>c', 'exaile -t',   _('Toggle Play/Pause:')),
    ('stop',        '<Super>v', 'exaile -s',   _('Stop:')),
    ('previous',    '<Super>z', 'exaile -p',   _('Previous Song:')),
    ('next',        '<Super>b', 'exaile -n',   _('Next Song:')),
    ('ivolume',     '<Super>i', 'exaile -i 5', _('Increase Volume:')),
    ('dvolume',     '<Super>d', 'exaile -l 5', _('Decrease Volume:'))
)

# some shortcuts
_keyb = lambda cmd: '/apps/metacity/global_keybindings/run_command_%d' % cmd
_keyc = lambda cmd: '/apps/metacity/keybinding_commands/command_%d' % cmd
keyb = lambda c, cmd: c.get_string(_keyb(cmd))
keyc = lambda c, cmd: c.get_string(_keyc(cmd))
skeyb = lambda c, cmd, value: c.set_string(_keyb(cmd), value)
signal_id = None

def destroy():
    """
        Called when the plugin is disabled
    """
    global signal_id
    c = gconf.client_get_default()
    for i, v in enumerate(items):
        count = i + 20
        if keyc(c, count).find('exaile') > -1:
            c.unset(_keyb(count))
            c.unset(_keyc(count))

    if signal_id:
        gobject.source_remove(signal_id)
        signal_id = None

    return

def initialize():
    """
        Called when the plugin is enabled
    """
    global signal_id
    # TODO figure out if Metacity is the current window manager or not
    # Return False if metacity is not the current wm

    c = gconf.client_get_default()
    for i, v in enumerate(items):
        count = i + 20

        binding = APP.settings.get_str(v[0], default=v[1],
            plugin=plugins.name(__file__))

        # key binding
        c.set_string(_keyb(count), binding)

        # key command
        c.set_string(_keyc(count), v[2])

    signal_id = APP.connect('quit', lambda *e: destroy())

    return True

def configure():
    """
        Called when the user wants to configure the plugin
    """
    global t_count
    c = gconf.client_get_default()

    table = gtk.Table()
    table.set_border_width(8)
    fields = []
    t_count = 0
    
    def attach_field(label, value):
        global t_count
        label = gtk.Label(label)
        label.set_property('xalign', 1)
        label.set_padding(4, 4)

        input = gtk.Entry()
        input.set_text(value)
        table.attach(label, 0, 1, t_count, t_count + 1)
        table.attach(input, 1, 2, t_count, t_count + 1)
        fields.append(input)
        t_count += 1

    for i, v in enumerate(items):
        binding = APP.settings.get_str(v[0], default=v[1],
            plugin=plugins.name(__file__))
        attach_field(v[3], binding)

    frame = gtk.Frame(_('Set Hotkeys'))
    frame.set_border_width(8)
    frame.add(table)

    dlg = plugins.PluginConfigDialog(APP.window, PLUGIN_NAME)
    dlg.get_child().add(frame)
    dlg.show_all()
    response = dlg.run()
    dlg.hide()

    if response == gtk.RESPONSE_OK:
        for i, v in enumerate(items):
            if PLUGIN_ENABLED: skeyb(c, i + 20, fields[i].get_text())
            APP.settings.set_str(v[0], fields[i].get_text())
