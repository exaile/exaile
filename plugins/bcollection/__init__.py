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
import xl

import _monitor
import _panel
import _preferences

class PluginClass(object):
    """
        Plugin Class
    """
    def enable(self, exaile):
        self.__exaile = exaile

    def on_gui_loaded(self):

        self.__panel = _panel.MainPanel(self.__exaile)
        xl.providers.register('main-panel', self.__panel)

        _monitor.start()

    def disable(self, _exaile):
        _monitor.stop()

        xl.providers.unregister('main-panel', self.__panel)
        del self.__panel

    def get_preferences_pane(self):
        return _preferences


#: PluginClass: Exaile's definition
plugin_class = PluginClass
