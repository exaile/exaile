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
# along with Spydaap. If not, see <https://www.gnu.org/licenses/>.

import http.server
import socketserver
import logging
import select
import socket
import os

import spydaap
import spydaap.daap
import spydaap.metadata
import spydaap.containers
import spydaap.cache
import spydaap.server
import spydaap.zeroconfimpl

from xl import common, event, xdg

# Notes for debugging:
# You might want to run
#    handle SIGPIPE nostop
# when debugging this code in gdb.

"""
Notes for hunting down errors:
If you run this plugin and a client stops playback on any file, expect this
traceback:

    Exception happened during processing of request from ('192.168.122.1', 34394)
    Traceback (most recent call last):
      File "/usr/lib64/python2.7/SocketServer.py", line 596, in process_request_thread
        self.finish_request(request, client_address)
      File "/usr/lib64/python2.7/SocketServer.py", line 331, in finish_request
        self.RequestHandlerClass(request, client_address, self)
      File "/usr/lib64/python2.7/SocketServer.py", line 654, in __init__
        self.finish()
      File "/usr/lib64/python2.7/SocketServer.py", line 713, in finish
        self.wfile.close()
      File "/usr/lib64/python2.7/socket.py", line 283, in close
        self.flush()
      File "/usr/lib64/python2.7/socket.py", line 307, in flush
        self._sock.sendall(view[write_offset:write_offset+buffer_size])
    error: [Errno 32] broken pipe

This traceback is a result of getting a SIGPIPE, which is expected. The fact
that it is not being handled in the python standard library is a bug which has
been reported to https://bugs.python.org/issue14574
See also: https://stackoverflow.com/questions/6063416/
"""


logger = logging.getLogger('daapserver')

__all__ = ['DaapServer']


class MyThreadedHTTPServer(socketserver.ThreadingMixIn, http.server.HTTPServer):
    """Handle requests in a separate thread."""

    timeout = 1
    daemon_threads = True

    def __init__(self, *args):
        if ':' in args[0][0]:
            self.address_family = socket.AF_INET6
        http.server.HTTPServer.__init__(self, *args)


class DaapServer:
    def __init__(self, library, name=spydaap.server_name, host='', port=spydaap.port):
        #        Thread.__init__(self)
        self.host = host
        self.port = port
        self.library = library
        self.name = name
        self.httpd = None
        self.handler = None
        self.__cache = spydaap.cache.Cache(os.path.join(xdg.cache_home, 'daapserver'))
        self.__cache.clean()

        # Set a callback that will let us propagate library changes to clients
        event.add_callback(self.update_rev, 'libraries_modified', library.collection)

    def update_rev(self, *args):
        if self.handler is not None:
            # Updating the server revision, so if a client checks
            # it can see the library has changed
            self.handler.daap_server_revision += 1
            logger.info(
                'Libraries Changed, incrementing revision to %d.'
                % self.handler.daap_server_revision
            )
        self.__cache.clean()

    def set(self, **kwargs):
        for key in kwargs:
            setattr(self, key, kwargs[key])

    @common.threaded
    def run(self):
        self.zeroconf = spydaap.zeroconfimpl.ZeroconfImpl(
            self.name, self.port, stype="_daap._tcp"
        )
        self.handler = spydaap.server.makeDAAPHandlerClass(
            str(self.name), self.__cache, self.library, []
        )
        self.httpd = MyThreadedHTTPServer((self.host, self.port), self.handler)

        # signal.signal(signal.SIGTERM, make_shutdown(httpd))
        # signal.signal(signal.SIGHUP, rebuild_cache)
        if self.httpd.address_family == socket.AF_INET:
            self.zeroconf.publish(ipv4=True, ipv6=False)
        else:
            self.zeroconf.publish(ipv4=False, ipv6=True)

        try:
            try:
                logger.info("DAAP server: Listening.")
                self.httpd.serve_forever()
            except select.error:
                pass
        except KeyboardInterrupt:
            self.httpd.shutdown()

        logger.info("DAAP server: Shutting down.")
        self.zeroconf.unpublish()
        self.httpd = None

    def start(self):
        if self.httpd is None:
            self.run()
            return True
        return False

    def stop(self):
        if self.httpd is not None:
            self.httpd.shutdown()
            self.httpd.socket.close()
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
#    zeroconf = spydaap.zeroconfimpl.ZeroconfImpl(spydaap.server_name,
#                                         spydaap.port,
#                                         stype="_daap._tcp")
#    zeroconf.publish()
#    logger.warning("Listening.")
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
#    logger.warning("Shutting down.")
#    zeroconf.unpublish()

# def main():
#    really_main()

# if __name__ == "__main__":
#    main()
