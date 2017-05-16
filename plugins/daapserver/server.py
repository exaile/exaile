# Modified to work with Exaile - Brian Parma
#
# Copyright (C) 2008 Erik Hetzner

# This file is part of Spydaap. Spydaap is free software: you can
# redistribute it and/or modify it under the terms of the GNU General
# Public License as published by the Free Software Foundation, either
# version 3 of the License, or (at your option) any later version.

# Spydaap is distributed in the hope that it will be useful, but
# WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE. See the GNU
# General Public License for more details.

# You should have received a copy of the GNU General Public License
# along with Spydaap. If not, see <http://www.gnu.org/licenses/>.

import BaseHTTPServer
import SocketServer
import getopt
import grp
import httplib
import logging
import os
import pwd
import select
import signal
import spydaap
import sys
import socket
import spydaap.daap
import spydaap.metadata
import spydaap.containers
import spydaap.cache
import spydaap.server
import spydaap.zeroconf
from spydaap.daap import do
from threading import Thread
from xl import common, event
import config

# logging.basicConfig()
logger = logging.getLogger('daapserver')

__all__ = ['DaapServer']


class MyThreadedHTTPServer(SocketServer.ThreadingMixIn, BaseHTTPServer.HTTPServer):
    """Handle requests in a separate thread."""
    timeout = 1

    def __init__(self, *args):
        if ':' in args[0][0]:
            self.address_family = socket.AF_INET6
        BaseHTTPServer.HTTPServer.__init__(self, *args)
        self.keep_running = True

    def serve_forever(self):
        while self.keep_running:
            self.handle_request()

    def force_stop(self):
        self.keep_running = False
        self.server_close()


class DaapServer():

    def __init__(self, library, name=spydaap.server_name, host='', port=spydaap.port):
        #        Thread.__init__(self)
        self.host = host
        self.port = port
        self.library = library
        self.name = name
        self.httpd = None
        self.handler = None

        # Set a callback that will let us propagate library changes to clients
        event.add_callback(self.update_rev, 'libraries_modified',
                           library.collection)

    def update_rev(self, *args):
        if self.handler is not None:
            # Updating the server revision, so if a client checks
            # it can see the library has changed
            self.handler.daap_server_revision += 1
            logger.info('Libraries Changed, incrementing revision to %d.'
                        % self.handler.daap_server_revision)

    def set(self, **kwargs):
        for key in kwargs:
            setattr(self, key, kwargs[key])

    @common.threaded
    def run(self):
        self.zeroconf = spydaap.zeroconf.Zeroconf(self.name,
                                                  self.port,
                                                  stype="_daap._tcp")
        self.handler = spydaap.server.makeDAAPHandlerClass(
            str(self.name), [], self.library, [])
        self.httpd = MyThreadedHTTPServer((self.host, self.port),
                                          self.handler)

        #signal.signal(signal.SIGTERM, make_shutdown(httpd))
        #signal.signal(signal.SIGHUP, rebuild_cache)
        if self.httpd.address_family == socket.AF_INET:
            self.zeroconf.publish(ipv4=True, ipv6=False)
        else:
            self.zeroconf.publish(ipv4=False, ipv6=True)

        try:
            try:
                logger.warning("Listening.")
                self.httpd.serve_forever()
            except select.error:
                pass
        except KeyboardInterrupt:
            self.httpd.force_stop()

        logger.warning("Shutting down.")
        self.zeroconf.unpublish()
        self.httpd = None

    def start(self):
        if self.httpd is None:
            self.run()
            return True
        return False

    def stop(self):
        if self.httpd is not None:
            self.httpd.force_stop()
            return True
        return False

    def stop_server(self):
        self.stop()

# def rebuild_cache(signum=None, frame=None):
#    md_cache.build(os.path.abspath(spydaap.media_path))
#    container_cache.clean()
#    container_cache.build(md_cache)
#    cache.clean()

# def really_main():
#    rebuild_cache()
#    zeroconf = spydaap.zeroconf.Zeroconf(spydaap.server_name,
#                                         spydaap.port,
#                                         stype="_daap._tcp")
#    zeroconf.publish()
#    logger.warn("Listening.")
#    httpd = MyThreadedHTTPServer(('0.0.0.0', spydaap.port),
#                                 spydaap.server.makeDAAPHandlerClass(spydaap.server_name, cache, md_cache, container_cache))
#
##    signal.signal(signal.SIGTERM, make_shutdown(httpd))
##    signal.signal(signal.SIGHUP, rebuild_cache)
#
#    try:
#        try:
#            httpd.serve_forever()
#        except select.error:
#            pass
#    except KeyboardInterrupt:
#        httpd.force_stop()
#    logger.warn("Shutting down.")
#    zeroconf.unpublish()

# def main():
#    really_main()

# if __name__ == "__main__":
#    main()
