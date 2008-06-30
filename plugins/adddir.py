"""
	Add Directory Plugin
	
	With this plugin you can select folders instead of files to add
	to your playlist.
	
	Created By Lucas van Dijk <info@return.net> (http://www.retun1.net)
"""
 
import gtk
from xl import xlmisc
from xl import media, library
import xl.plugins as plugins
from gettext import gettext as _
import os, os.path
 
PLUGIN_NAME = _("Add Directory")
PLUGIN_AUTHORS = ['Lucas van Dijk <info@return1.net> (http://www.return1.net)']
PLUGIN_VERSION = '0.1'
PLUGIN_DESCRIPTION = _("With this plugin you can select folders instead of files to add to your playlist.")
PLUGIN_ENABLED = False
 
b = gtk.Button()
PLUGIN_ICON = b.render_icon(gtk.STOCK_OPEN, gtk.ICON_SIZE_MENU)
b.destroy()
 
def initialize():
	"""
		Called when the plugin is enabled
	"""
	
	# Add Menu entry
	try:
		menu_item = gtk.MenuItem(_('Open Directory'))	
		menu_item.connect('activate', on_add_dir)
		menu_item.set_name('add_dir_plugin_item')
		
		menubar = APP.xml.get_widget('file_menu_menu')	
		menubar.insert(menu_item, 3)
		
		menu_item.show()
	except Exception, e:
		print e
	return True
 
def destroy():
	"""
		Called when the plugin is disabled
	"""
	menubar = APP.xml.get_widget('file_menu_menu')
	for child in menubar.get_children():
		if child.get_name() == 'add_dir_plugin_item':
			menubar.remove(child)
			
class TrackDataEx(library.TrackData):
	"""
		This subclass allows merging of 2 TrackData instances
	"""
	
	def append(self, tracks):
		if isinstance(tracks, library.TrackData):
			for track in tracks:
				library.TrackData.append(self, track)
		else:
			library.TrackData.append(self, tracks)
		
 
def on_add_dir(item, event = None):	
	dialog = gtk.FileChooserDialog(_("Choose directories"), APP.window, gtk.FILE_CHOOSER_ACTION_SELECT_FOLDER, (gtk.STOCK_CANCEL, gtk.RESPONSE_CANCEL, gtk.STOCK_OPEN, gtk.RESPONSE_OK))
		
	hbox = gtk.HBox(True)
	
	new_tab = gtk.CheckButton(_("Open in new tab"))
	recurse = gtk.CheckButton(_("Recursive"))
	recurse.set_active(True)
	
	hbox.pack_start(new_tab)
	hbox.pack_start(recurse)
	hbox.show_all()
	
	dialog.set_extra_widget(hbox)
	dialog.set_current_folder(APP.get_last_dir())
	dialog.set_select_multiple(True)

	music = gtk.FileFilter()
	music.set_name(_("Music Files"))
	all = gtk.FileFilter()
	all.set_name(_("All Files"))

	for ext in media.SUPPORTED_MEDIA:
		music.add_pattern('*' + ext)
		
	all.add_pattern('*')

	dialog.add_filter(music)
	dialog.add_filter(all)

	result = dialog.run()
	dialog.hide()
	
	if result == gtk.RESPONSE_OK:
		paths = dialog.get_filenames()
		dir = dialog.get_current_folder()
		if dir: # dir is None when the last view is a search
			APP.last_open_dir = dir
		APP.status.set_first(_("Populating playlist..."))	
		
		songs = TrackDataEx()
		for dir in paths:
			songs_to_append = import_dir(dir, new_tab.get_active(), recurse.get_active())
			
			if songs_to_append:
				songs.append(songs_to_append)
		
		if songs:
			if new_tab.get_active():
				APP.new_page(_("Playlist"), songs)
			else:
				APP.playlist_manager.append_songs(songs)
				
def import_dir(dir, new_tab, recurse):
	songs = TrackDataEx()
	count = 0
	
	for file in os.listdir(dir):
		path = os.path.join(dir, file)
		
		if os.path.isdir(path):
			if recurse:
				songs_to_append = import_dir(path, new_tab, recurse)
				if songs_to_append:
					songs.append(songs_to_append)
		else:
			(f, ext) = os.path.splitext(path)
			if ext in media.SUPPORTED_MEDIA:
				if count >= 10:
					xlmisc.finish()
					count = 0
				tr = library.read_track(APP.db, APP.all_songs, path)

				count += 1
				if tr:
					songs.append(tr)	
	return songs
