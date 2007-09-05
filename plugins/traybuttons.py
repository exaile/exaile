#!/usr/bin/env python
# Copyright (C) 2006 Andras Petrik <bikmak@gmail.com>
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

import gtk, gobject, pygtk
from gettext import gettext as _
import xl.plugins as plugins

PLUGIN_NAME = _("Tray Buttons")
PLUGIN_AUTHORS = ['Andras Petrik <bikmak@gmail.com>']
PLUGIN_VERSION = '0.7.2'
PLUGIN_DESCRIPTION = _(r"""This plugin adds "Play/Pause", "Previous" and "Next" buttons to the notification area""")
PLUGIN_ENABLED = False
PLUGIN_ICON = None

PLUGIN = None

CONNS = plugins.SignalContainer()

class Plugin:
	
	"""
		It represents the class for the plugin
	"""
	
	
	def __init__(self, app):
		
		self.app = app
		self.buttonReverse = app.settings.get_boolean( 'button_reverse', plugin=plugins.name(__file__), default = False )
		
		if ( self.buttonReverse == False ) :
			self.tyPrevious = gtk.status_icon_new_from_stock( "gtk-media-previous" )
			self.tyPause = gtk.status_icon_new_from_stock( "gtk-media-pause" )
			self.tyNext = gtk.status_icon_new_from_stock( "gtk-media-next" )
		else :
			self.tyNext = gtk.status_icon_new_from_stock( "gtk-media-next" )
			self.tyPause = gtk.status_icon_new_from_stock( "gtk-media-pause" )
			self.tyPrevious = gtk.status_icon_new_from_stock( "gtk-media-previous" )
			
		
		self.tyPrevious.connect( "activate", self.onPrevious, None )
		self.tyPrevious.set_tooltip( _("Previous Track") )
		
		self.tyPause.connect( "activate", self.onPause, None )
		self.tyPause.set_tooltip( _("Play/Pause") )
		
		self.tyNext.connect( "activate", self.onNext, None )
		self.tyNext.set_tooltip( _("Next Track") )	
		
		self.tyPrevious.set_visible( app.settings.get_boolean( 'previous_visible', plugin=plugins.name( __file__ ), default = True ) )
		self.tyPause.set_visible( app.settings.get_boolean( 'pause_visible', plugin=plugins.name( __file__ ), default = True ) )
		self.tyNext.set_visible( app.settings.get_boolean( 'next_visible', plugin=plugins.name( __file__ ), default = True ) )
		self.showTrackInformation = app.settings.get_boolean( 'show_track_information', plugin=plugins.name(__file__), default = True )
	
	def onPause( self, par1, par2 ):
		"""
			Called when toggle pause icon is clicked
		"""
		self.app.player.toggle_pause()
		self.setPauseIcon()

	def onPrevious( self, par1, par2 ):
		"""
			Called when previous icon is clicked
		"""
		self.app.player.previous()
	
	def onNext( self, par1, par2 ):
		"""
			Called when next icon is clicked
		"""
		self.app.player.next()
		
	def destroy( self ):
		"""
			destroy the object?! ???
		"""
		
		self.tyPause.set_visible( False )
		self.tyPrevious.set_visible( False )
		self.tyNext.set_visible( False )
		
	def setPauseVisible( self, visible ) :
		"""
			set the visibility of the pause icon
		"""
		self.tyPause.set_visible( visible )
	
	def setPreviousVisible( self, visible ) :
		"""
			set the visibility of the previous icon
		"""
		self.tyPrevious.set_visible( visible )
		
	def setNextVisible( self, visible ) :
		"""
			set the visibility of the next icon
		"""
		self.tyNext.set_visible( visible )
		
	def setPauseIcon( self ) :
		"""
			Set the picture of the play/pause icon
		"""
		if APP.player.is_paused():
			self.tyPause.set_from_stock( "gtk-media-play" )
			self.tyPause.set_tooltip( _("Play") )
		else:
			self.tyPause.set_from_stock( "gtk-media-pause" )
			self.tyPause.set_tooltip( _("Pause") )
		
	def setShowTrackInformation( self, inp ) :
		"""
			set the showTrackInformation variable
		"""
		self.showTrackInformation = inp
		if ( inp == False ) :
			self.tyPrevious.set_tooltip( _("Previous Track") )
			self.tyNext.set_tooltip( _("Next Track") )
		
	def getShowTrackInformation( self ) :
		"""
			return with the showTrackInformation variable's value
		"""
		return self.showTrackInformation
		
	def setNextTooltip( self, current ) :
		"""
			Set the tooltip of the next icon
		"""
		
		self.tyPrevious.set_tooltip(_("Previous track: %(title)s by %(artist)s") % {
      'title' : self.app.tracks.get_previous_track( current ).title,
      'artist' : self.app.tracks.get_previous_track( current ).artist
    })
		
	def setPreviousTooltip( self, current ) :
		"""
			Set the tooltip of the previous icon
		"""
		self.tyNext.set_tooltip(_("Next track: %(title)s by %(artist)s") % {
      'title' : self.app.tracks.get_next_track( current ).title,
      'artist' : self.app.tracks.get_next_track( current ).artist
    })



def initialize():
	"""
		Called when the plugin is enabled
	"""
	global APP, PLUGIN
	if ( PLUGIN == None ) :
		PLUGIN = Plugin( APP )
	else :
		PLUGIN.setPauseVisible( True )
		PLUGIN.setPreviousVisible( True )
		PLUGIN.setNextVisible( True )
	CONNS.connect( APP.player, 'pause-toggled', pause_toggled )
	CONNS.connect( APP.player, 'play-track', play_track )
	return True

def destroy():
	"""
		Called when the plugin is disabled
	"""
	
	global PLUGIN
	PLUGIN.destroy()
	
def configure():
	"""
		Configuration Window
	"""
		
	global APP, PLUGIN
	
	settings = APP.settings
	dialog = plugins.PluginConfigDialog( APP.window, PLUGIN_NAME )
	box = dialog.main

	pauseVisible = settings.get_boolean( 'pause_visible', plugin=plugins.name(__file__), default = True )
	nextVisible = settings.get_boolean( 'next_visible', plugin=plugins.name(__file__), default = True )
	previousVisible = settings.get_boolean( 'previous_visible', plugin=plugins.name(__file__), default = True )
	showTrackInformation = settings.get_boolean( 'show_track_information', plugin=plugins.name(__file__), default = True )
	buttonReverse = settings.get_boolean( 'button_reverse',  plugin=plugins.name(__file__), default = False )

	pauseVisibleBox = gtk.CheckButton( _('Pause/Play icon') )
	nextVisibleBox = gtk.CheckButton( _('Next icon') )
	previousVisibleBox = gtk.CheckButton( _('Previous icon') )
	showTrackInformationBox = gtk.CheckButton( _('Show track information in the tooltip of Next and Previous') )
	buttonReverseBox = gtk.CheckButton( _('Reverse the order of the Next and Previous buttons (requires a restart of Exaile)') )

	pauseVisibleBox.set_active( pauseVisible )
	nextVisibleBox.set_active( nextVisible )
	previousVisibleBox.set_active( previousVisible )
	showTrackInformationBox.set_active( showTrackInformation )
	buttonReverseBox.set_active( buttonReverse )

	box.pack_start( pauseVisibleBox )
	box.pack_start( nextVisibleBox )
	box.pack_start( previousVisibleBox )
	box.pack_start( showTrackInformationBox )
	box.pack_start( buttonReverseBox )
	dialog.show_all()

	result = dialog.run()
	dialog.hide()

	settings.set_boolean( 'pause_visible', pauseVisibleBox.get_active(), plugin=plugins.name(__file__) )
	settings.set_boolean( 'next_visible', nextVisibleBox.get_active(), plugin=plugins.name(__file__) )
	settings.set_boolean( 'previous_visible', previousVisibleBox.get_active(), plugin=plugins.name(__file__) )
	settings.set_boolean( 'show_track_information', showTrackInformationBox.get_active(), plugin=plugins.name(__file__) )
	settings.set_boolean( 'button_reverse', buttonReverseBox.get_active(), plugin=plugins.name(__file__) )
	
	PLUGIN.setPauseVisible( pauseVisibleBox.get_active() )
	PLUGIN.setNextVisible( nextVisibleBox.get_active() )
	PLUGIN.setPreviousVisible( previousVisibleBox.get_active() )
	PLUGIN.setShowTrackInformation( showTrackInformationBox.get_active() )
	
def pause_toggled( exaile, track ):
	"""
		Called when pause is toggled
	"""
	
	global PLUGIN
	
	PLUGIN.setPauseIcon()
	
def play_track( exaile, track ):
	"""
		Called when playback on a track starts ("play-track" event)
	"""
	global PLUGIN
	global APP
	
	if ( PLUGIN.getShowTrackInformation() == True ) :
		if ( APP.tracks.get_next_track( track ) != None ) :
			PLUGIN.setNextTooltip( track )
		if ( APP.tracks.get_previous_track( track ) != None ) :
			PLUGIN.setPreviousTooltip( track )
