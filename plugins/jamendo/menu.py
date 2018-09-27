from xl.nls import gettext as _
from xlgui.widgets import menu


class JamendoMenu(menu.Menu):
    def __init__(self, parent):
        menu.Menu.__init__(self, parent)

        self.add_item(
            menu.simple_menu_item(
                'append',
                [],
                _('Append to Current'),
                'gtk-add',
                callback=lambda *args: parent.add_to_playlist(),
            )
        )

        # self.add_item(menu.simple_menu_item('download', ['append'], _('Download to Library'), 'gtk-save',
        #                        callback=lambda *args: parent.add_to_playlist()))
