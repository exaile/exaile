# Copyright (C) 2007 Mathieu Virbel <tito@bankiz.org>
#
# This program is free software; you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation; either version 1, or (at your option)
# any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program; if not, write to the Free Software
# Foundation, Inc., 675 Mass Ave, Cambridge, MA 02139, USA.

import gtk, threading, gobject, cgi
from gettext import gettext as _
from BaseHTTPServer import BaseHTTPRequestHandler, HTTPServer

PLUGIN_NAME = _('HTTP Server Control')
PLUGIN_AUTHORS = ['Mathieu Virbel <tito@bankiz.org>']
PLUGIN_VERSION = '0.2'
PLUGIN_DESCRIPTION = _('Open an HTTP Server to control exaile from a remote host')
PLUGIN_ENABLED = False
button = gtk.Button()
PLUGIN_ICON = button.render_icon('gtk-info', gtk.ICON_SIZE_MENU)
button.destroy()

DEFAULT_PORT = 10000

APP = None
eh_thread = None



# -----------------------------------------------------------------------------
# Utilities
# -----------------------------------------------------------------------------

def tag(tagname, value):
	"""
		Construct a xml tag
	"""
	return '<%s>%s</%s>' % (tagname, value, tagname)

class TrackInfo:
	"""
		Fetch some infos from a Track
		(In case we have no track, set some default value)
		(We also can have reduce information for display a playlist)
	"""

	def __init__(self, track = None, playlistmode=False):
		self.infos = {}
		self.infos['filename']	= ''
		self.infos['title']		= _('None')
		self.infos['artist']	= _('None')
		self.infos['album']		= _('None')
		self.infos['bitrate']	= _('None')
		self.infos['rating']	= _('Unknown')
		self.infos['len']		= '0:00'
		self.infos['disc']		= _('None')
		self.infos['genre']		= _('None')
		self.infos['duration']	= '0'
		self.infos['is_paused']	= APP.player.is_paused()
		self.infos['is_playing']= APP.player.is_playing()

		if track is not None:
			self.infos['filename'] = cgi.escape(track.get_filename())
			self.infos['title'] = cgi.escape(track.get_title())
			self.infos['artist'] = cgi.escape(track.get_artist())
			self.infos['album'] = cgi.escape(track.get_album())
			self.infos['bitrate'] = cgi.escape(track.get_bitrate())
			self.infos['rating'] = cgi.escape(track.get_rating())
			self.infos['len'] = cgi.escape(track.get_len())
			self.infos['disc'] = cgi.escape(track.get_disc())
			self.infos['genre'] = cgi.escape(track.get_genre())
			self.infos['duration'] = cgi.escape(str(track.get_duration()))

		if not playlistmode:
			self.infos['position'] = '0'
			if track is not None:
				self.infos['position'] = cgi.escape(str(APP.player.get_current_position()))



# -----------------------------------------------------------------------------
# Callbacks for HTTP Request
# -----------------------------------------------------------------------------

def eh_page_rpc_current(r):
	"""
		Get informations from current track
		Response is in XML.
	"""
	r.send_response(200, 'OK')
	r.send_header('Pragma', 'no-cache')
	r.send_header('Content-type', 'text/xml; charset=utf-8')
	r.end_headers()

	ti = TrackInfo(APP.player.current)
	r.wfile.write('<?xml version="1.0"?>')
	r.wfile.write('<track>')
	for key in ti.infos:
		r.wfile.write(tag(key, ti.infos[key]))
	r.wfile.write('</track>')


def eh_page_cover_current(r):
	"""
		Return the current track cover in a HTTP Response
		Support only jpeg or png file
	"""
	track = APP.player.current
	if track is None:
		r.send_error(404,'Not Found')
		return
	filename = APP.cover_manager.fetch_cover(track, 1)
	if filename is None or filename == '':
		r.send_error(404, 'Not Found')
		return

	handle = open(filename, 'rb')
	if handle is None:
		self.send_error(404, 'Not Found')
		return

	r.send_response(200, 'OK')
	r.send_header('Pragma', 'no-cache')
	if filename.rfind('.jpg') > 0:
		r.send_header('Content-type', 'image/jpeg')
	else:
		r.send_header('Content-type', 'image/png')
	r.end_headers()

	data = handle.read()
	handle.close()

	r.wfile.write(data)


def eh_page_file(r):
	"""
		Return a static file from zipfile
		Filter is done before.
	"""
	r.send_response(200, 'OK')
	r.send_header('Pragma', 'no-cache')
	if r.path.rfind('.css') > 0:
		r.send_header('Content-type', 'text/css')
	else:
		r.send_header('Content-type', 'text/html; charset=utf-8')
	r.end_headers()

	path = r.path
	if path == '/':
		path = '/index.html'

	data = ZIP.get_data('data%s' % path)
	r.wfile.write(data)


def eh_page_rpc_action(r):
	"""
		Handle some player action (play, next, pause...)
	"""
	r.send_response(200, 'OK')
	r.send_header('Pragma', 'no-cache')
	r.send_header('Content-type', 'text/plain')
	r.end_headers()
	r.wfile.write('OK')

	paths = r.path.split('?')
	path = paths[0]
	if path == '/rpc/action/play':
		if len(paths) > 1:
			args = cgi.parse_qs(paths[1])
			if args.has_key('f') and args['f'] != '' and APP.tracks is not None:
				songs = APP.tracks.get_songs()
				for track in songs:
					if track.get_filename() == args['f'][0]:
						print 'PLAYING filename=%s' % args['f'][0]
						gobject.idle_add(APP.player.play_track, track, False, False)
						return;
		if APP.player.is_paused():
			gobject.idle_add(APP.player.toggle_pause)
		else:
			gobject.idle_add(APP.player.play)
	elif path == '/rpc/action/next':
		gobject.idle_add(APP.player.next)
	elif path == '/rpc/action/previous':
		gobject.idle_add(APP.player.previous)
	elif path == '/rpc/action/pause':
		gobject.idle_add(APP.player.pause)
	elif path == '/rpc/action/stop':
		gobject.idle_add(APP.player.stop)
	elif path == '/rpc/action/seek':
		args = cgi.parse_qs(paths[1])
		if args.has_key('s') and args['s'] != '':
			gobject.idle_add(APP.player.seek, int(args['s'][0]), False)


def eh_page_playlist_list(r):
	"""
		Return track informations from current playlist
	"""
	r.send_response(200, 'OK')
	r.send_header('Pragma', 'no-cache')
	r.send_header('Content-type', 'text/xml; charset=utf-8')
	r.end_headers()

	r.wfile.write('<?xml version="1.0"?>')
	r.wfile.write('<playlist>')
	if APP.tracks is not None:
		songs = APP.tracks.get_songs()
		for song in songs:
			ti = TrackInfo(song, playlistmode=True)
			r.wfile.write('<track>')
			for key in ti.infos:
				r.wfile.write(tag(key, ti.infos[key]))
			r.wfile.write('</track>')
	r.wfile.write('</playlist>')



# -----------------------------------------------------------------------------
# HTTP server
# -----------------------------------------------------------------------------

eh_pages = {
		# Dynamic content
		'/image/cover/current':	eh_page_cover_current,

		# RPC url
		'/rpc/current':			eh_page_rpc_current,
		'/rpc/action/play':		eh_page_rpc_action,
		'/rpc/action/stop':		eh_page_rpc_action,
		'/rpc/action/next':		eh_page_rpc_action,
		'/rpc/action/previous':	eh_page_rpc_action,
		'/rpc/action/pause':	eh_page_rpc_action,
		'/rpc/action/seek':		eh_page_rpc_action,
		'/rpc/playlist/list':	eh_page_playlist_list,

		# Data
		'/':					eh_page_file,
		'/index.html':			eh_page_file,
		'/exaile.css':			eh_page_file,
		'/exaile.js':			eh_page_file,
		'/prototype.js':		eh_page_file,
		'/btn-play.png':		eh_page_file,
		'/btn-stop.png':		eh_page_file,
		'/btn-pause.png':		eh_page_file,
		'/btn-previous.png':	eh_page_file,
		'/btn-next.png':		eh_page_file,
		'/btn-reload.png':		eh_page_file,
		'/star.png':			eh_page_file,
		'/loading.gif':			eh_page_file,
		'/bg-trans.png':		eh_page_file,
	}

class ExaileHttpRequestHandler(BaseHTTPRequestHandler):

	def do_GET(self):

		path = self.path.split('?')[0]
		if eh_pages.has_key(path):
			eh_pages[path](self)
		else:
			self.send_error(404,'Not Found')
			return

		return

	@staticmethod
	def serve_forever(port):
		HTTPServer(('', port), ExaileHttpRequestHandler).serve_forever()

class ExaileHttpThread(threading.Thread):

	def __init__(self):
		threading.Thread.__init__(self)

	def run(self):
		print 'HTTP> http://127.0.0.1:%d/' % DEFAULT_PORT
		ExaileHttpRequestHandler.serve_forever(DEFAULT_PORT)



# -----------------------------------------------------------------------------
# Exaile interface
# -----------------------------------------------------------------------------

def initialize():
	eh_thread = ExaileHttpThread()
	eh_thread.setDaemon(True)
	eh_thread.start()
	return True

def destroy():
	if eh_thread is not None:
		del eh_thread
		eh_thread = None
