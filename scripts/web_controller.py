#!/usr/bin/env python

# web_controller - Simple Web server to control Exaile
# Copyright (c) 2007 Johannes Sasongko <sasongko@gmail.com>
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

"""Simple Web server to control Exaile.

Usage: web_controller [port [exaile_executable]]

Note that this server is not secured at all other than by a strict limitation of
the available commands.  Anyone with access to the server will still be able to
control playback.
"""

from subprocess import *
from BaseHTTPServer import *

class ExaileHttpHandler(BaseHTTPRequestHandler):
	allowed_commands = ['prev', 'play', 'play-pause', 'stop', 'next', 'query']

	def do_GET(self):
		self.send_response(200)
		self.send_header('Content-type', 'text/html')
		self.end_headers()

		write = self.wfile.write
		write('<html><head><title>Exaile</title><body>')

		write('<pre>')
		command = self.path[1:]
		if command and command in self.allowed_commands:
			line = [self.server.exaile, '--' + command]
			print 'Running', line
			write(Popen(line, stdout=PIPE).communicate()[0])
		write('</pre>')

		write('<ul>')
		for cmd in self.allowed_commands:
			write('<li><a href="' + cmd + '">' + cmd + '</a></li>')
		write('</ul>')

		write('</body></html>')

def run(port, exaile):
	server = None
	try:
		server = HTTPServer(('', port), ExaileHttpHandler)
		server.exaile = exaile
		server.serve_forever()
	except KeyboardInterrupt:
		if server:
			server.socket.close()
	except:
		if server:
			server.socket.close()
		raise

if __name__ == '__main__':
	from sys import argv
	argc = len(argv)
	port = 8080
	exaile = 'exaile'
	if argc > 1:
		port = int(argv[1])
		if argc > 2:
			exaile = argv[2]
	run(port, exaile)
