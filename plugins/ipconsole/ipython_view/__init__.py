# Copyright (C) 2012 Brian Parma
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
import logging

logger = logging.getLogger(__name__)

try:
    import IPython
    version = IPython.__version__
    
    from ipython_view import IPythonView

except (ImportError, AttributeError):
    logger.error('could not find a compatible version of IPython', exc_info=True)
    
    
if __name__ == '__main__':
    import gtk

    w = gtk.Window()
    w.set_title('Example IPythonView')
    
    sw = gtk.ScrolledWindow()
    sw.set_policy(gtk.POLICY_AUTOMATIC, gtk.POLICY_AUTOMATIC)
    
    ipv = IPythonView()
    ipv.set_wrap_mode(gtk.WRAP_CHAR)
    ipv.modify_base(gtk.STATE_NORMAL, gtk.gdk.color_parse('black'))
    ipv.modify_text(gtk.STATE_NORMAL, gtk.gdk.color_parse('lavender'))
    #ipv.IP.magic_colors('Linux') # IPython color scheme
#    ipv.IP.user_ns.clear()
    w.add(sw)
    sw.add(ipv)
    
    w.set_default_size(640,320)
    w.show_all()
    
    w.connect('delete-event',gtk.main_quit)
    
    gtk.main()    

