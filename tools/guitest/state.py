"""Objects that manage the test fixture."""


class GuiState(object):
    """A singleton that stores miscellaneous info about the GUI fixture."""

    def __init__(self):
        self.reset()

    def reset(self):
        self.main = None
        self.level = 0 # number of recursive main() calls
        self.dlg_handler = None
        self.calls = []

    def set_main(self, main):
        self.main = main

    def set_dlg_handler(self, dlg_handler):
        self.dlg_handler = dlg_handler


guistate = GuiState()
