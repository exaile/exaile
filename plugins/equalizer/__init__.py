from xl import providers, event, settings
from xl.player.pipe import ElementBin

from xl.nls import gettext as _

import gst, gtk, gobject
import os

#xl.xdg.get_config_dir()

def __enb(eventname, exaile, nothing):
	gobject.idle_add(_enable, exaile)

def enable(exaile):
	if exaile.loading:
		event.add_callback(__enb, 'exaile_loaded')
	else:
		__enb(None, exaile, None)

def _enable(exaile):
	"""
	Called when plugin is loaded.
	"""
	global EQ_MAIN
	EQ_MAIN = EqualizerPlugin(exaile)

def disable(exaile):
	global EQ_MAIN
	EQ_MAIN.disable()
	EQ_MAIN = None

class GSTEqualizer(ElementBin):
	"""
	Equalizer GST class
	"""
	index = 20
	name = "equalizer-10bands"
	def __init__(self):
		ElementBin.__init__(self, name=self.name)
		self.audioconvert = gst.element_factory_make("audioconvert")
		self.elements[40] = self.audioconvert
		self.eq10band = gst.element_factory_make("equalizer-10bands")
		self.elements[50] = self.eq10band
		self.setup_elements()

		event.add_callback(self._on_setting_change, "plugin/equalizer_option_set")

	def _on_setting_change(self, name, object, data):
		for band in [0,1,2,3,4,5,6,7,8,9]:
			if data == "plugin/equalizer/band%s"%band:
				print "EQPLUGIN: Should have updated"
				print "EQPLUGIN: setting before: ", settings.get_option("plugin/equalizer/band%s"%band)
				print "EQPLUGIN: property before: ", self.eq10band.get_property("band%s"%band)
				self.eq10band.set_property("band%s"%band, settings.get_option("plugin/equalizer/band%s"%band))
				print "EQPLUGIN: property after: ", self.eq10band.get_property("band%s"%band)

class EqualizerPlugin:
	"""
	Equalizer plugin class
	"""

	def __init__(self, exaile):
		self.window = None
		providers.register("stream_element", GSTEqualizer)
		self.EQ = providers.MANAGER.get_providers(GSTEqualizer)

		self.MENU_ITEM = gtk.MenuItem(_('Equalizer'))
		self.MENU_ITEM.connect('activate', self.show_gui, exaile)
		exaile.gui.builder.get_object('tools_menu').append(self.MENU_ITEM)
		self.MENU_ITEM.show()

		self.presets = gtk.ListStore(str, int, int, int, int, int, int, int, int, int, int, int)
		self.load_presets()

		self.check_default_settings()

	def check_default_settings(self):

		for setting in [0,1,2,3,4,5,6,7,8,9]:
			if settings.get_option("plugin/equalizer/band%s"%setting) == None:
				settings.set_option("plugin/equalizer/band%s"%setting, 0.0)

		if settings.get_option("plugin/equalizer/pre") == None:
			settings.set_option("plugin/equalizer/pre", 0.0)

		if settings.get_option("plugin/equalizer/enabled") == None:
			settings.set_option("plugin/equalizer/enabled", True)


	def disable(self):
		providers.unregister("stream_element", GSTEqualizer)

		if self.MENU_ITEM:
			self.MENU_ITEM.hide()
			self.MENU_ITEM.destroy()
			self.MENU_ITEM = None

	def load_presets(self):
		"""
		Populate the GTK ListStore with presets
		"""
		self.presets.append(["Custom", 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0])
		self.presets.append(["Default", 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0])

	def show_gui(self, widget, exaile):
		"""
		Display main window.
		"""
		if self.window:
			self.window.present()
			return
		
		signals = {	'on_equalizer/main-window_destroy':self.destroy_gui,
				'on_equalizer/chk-enabled_toggled':self.toggle_enabled,
				'on_equalizer/combo-presets_changed':self.preset_changed,
				'on_equalizer/add-preset_activate':self.add_preset,
				'on_equalizer/remove-preset_activate':self.remove_preset,
				'on_equalizer/pre_format_value':self.adjust_preamp,
				'on_equalizer/band0_format_value':self.adjust_band,
				'on_equalizer/band1_format_value':self.adjust_band,
				'on_equalizer/band2_format_value':self.adjust_band,
				'on_equalizer/band3_format_value':self.adjust_band,
				'on_equalizer/band4_format_value':self.adjust_band,
				'on_equalizer/band5_format_value':self.adjust_band,
				'on_equalizer/band6_format_value':self.adjust_band,
				'on_equalizer/band7_format_value':self.adjust_band,
				'on_equalizer/band8_format_value':self.adjust_band,
				'on_equalizer/band9_format_value':self.adjust_band	}

		self.ui = gtk.Builder()
		self.ui.add_from_file( os.path.join( os.path.dirname(os.path.realpath(__file__)), 'equalizer.glade' ) )
		self.ui.connect_signals(signals)

		self.window = self.ui.get_object('equalizer/main-window')

		#Setup bands/preamp from current equalizer settings
		for x in (0,1,2,3,4,5,6,7,8,9):
			obj_name = "equalizer/band%s"%x
			self.ui.get_object(obj_name).set_value( self.get_band(x) )

		self.ui.get_object("equalizer/pre").set_value( self.get_pre() )

		#Put the presets into the presets combobox
		combobox = self.ui.get_object("equalizer/combo-presets")
		combobox.set_model(self.presets)
		combobox.set_text_column(0)
		combobox.set_active(0)

		self.ui.get_object('equalizer/chk-enabled').set_active( settings.get_option("plugin/equalizer/enabled") )

		self.window.show_all()

	def destroy_gui(self, widget):
		self.window = None

	def get_band(self, x):
		"""
		Get the current value of band x
		"""
		return settings.get_option("plugin/equalizer/band%s"%x)

	def get_pre(self):
		"""
		Get the current value of pre-amp
		"""
		return settings.get_option("plugin/equalizer/pre")

	#Widget callbacks

	def adjust_band(self, widget, data):
		"""
		Adjust the specified band
		"""
		settings.set_option("plugin/equalizer/band%s" %widget.get_name()[-1], widget.get_value())

	def adjust_preamp(self, widget, data):
		"""
		Adjust the preamp
		"""
		settings.set_option("plugin/equalizer/pre", widget.get_value())

	def add_preset(self, widget):
		pass
	
	def remove_preset(self, widget):
		pass
	
	def preset_changed(self, widget):
		
		d = widget.get_model()
		i = widget.get_active()

		#If an option other than "Custom" is chosen:
		if i > 0:
			
			self.ui.get_object("equalizer/pre").set_value( d.get_value( d.get_iter(i), 1) )

			for band in [0,1,2,3,4,5,6,7,8,9]:
				self.ui.get_object("equalizer/band%s"%band).set_value (d.get_value( d.get_iter(i), band+2) )

			widget.set_active(0)


	def toggle_enabled(self, widget):
		pass
