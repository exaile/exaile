# Copyright (C) 2009 Erik Hetzner

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
import errno
import logging
import os
import re
import urlparse
import socket
import spydaap
from spydaap.daap import do


def makeDAAPHandlerClass(server_name, cache, md_cache, container_cache):
    session_id = 1
    log = logging.getLogger('spydaap.server')

    class DAAPHandler(BaseHTTPServer.BaseHTTPRequestHandler):
        daap_server_revision = 1
        protocol_version = "HTTP/1.1"

        def h(self, data, **kwargs):
            self.send_response(kwargs.get('status', 200))
            self.send_header('Content-Type', kwargs.get('type', 'application/x-dmap-tagged'))
            self.send_header('DAAP-Server', 'Simple')
            self.send_header('Expires', '-1')
            self.send_header('Cache-Control', 'no-cache')
            self.send_header('Accept-Ranges', 'bytes')
            self.send_header('Content-Language', 'en_us')
            if 'extra_headers' in kwargs:
                for k, v in kwargs['extra_headers'].iteritems():
                    self.send_header(k, v)
            try:
                if isinstance(data, file):
                    self.send_header("Content-Length", str(os.stat(data.name).st_size))
                else:
                    self.send_header("Content-Length", len(data))
            except Exception:
                pass
            self.end_headers()
            if hasattr(self, 'isHEAD') and self.isHEAD:
                pass
            else:
                try:
                    if (hasattr(data, 'next')):
                        for d in data:
                            self.wfile.write(d)
                    else:
                        self.wfile.write(data)
                except socket.error, (err_no, err_str):
                    if err_no in [errno.ECONNRESET]:
                        # XXX: why do we need to pass this?
                        pass
                    else:
                        raise
            if (hasattr(data, 'close')):
                data.close()

        # itunes sends request for:
        # GET daap://192.168.1.4:3689/databases/1/items/626.mp3?seesion-id=1
        # so we must hack the urls; annoying.
        itunes_re = '^(?://[0-9]{1,3}\\.[0-9]{1,3}\\.[0-9]{1,3}\\.[0-9]{1,3}:[0-9]+)?'
        drop_q = '(?:\\?.*)?$'

        def do_GET(self):
            parsed_path = urlparse.urlparse(self.path).path
            if re.match(self.itunes_re + "/$", parsed_path):
                self.do_GET_login()
            elif re.match(self.itunes_re + '/server-info$', parsed_path):
                self.do_GET_server_info()
            elif re.match(self.itunes_re + '/content-codes$', parsed_path):
                self.do_GET_content_codes()
            elif re.match(self.itunes_re + '/databases$', parsed_path):
                self.do_GET_database_list()
            elif re.match(self.itunes_re + '/databases/([0-9]+)/items$', parsed_path):
                md = re.match(self.itunes_re + '/databases/([0-9]+)/items$', parsed_path)
                self.do_GET_item_list(md.group(1))
            elif re.match(self.itunes_re + '/databases/([0-9]+)/items/([0-9]+)\\.([0-9a-z]+)' + self.drop_q, parsed_path):
                md = re.match(self.itunes_re + '/databases/([0-9]+)/items/([0-9]+)\\.([0-9a-z]+)' + self.drop_q, parsed_path)
                self.do_GET_item(md.group(1), md.group(2), md.group(3))
            elif re.match(self.itunes_re + '/databases/([0-9]+)/containers$', parsed_path):
                md = re.match(self.itunes_re + '/databases/([0-9]+)/containers$', parsed_path)
                self.do_GET_container_list(md.group(1))
            elif re.match(self.itunes_re + '/databases/([0-9]+)/containers/([0-9]+)/items$', parsed_path):
                md = re.match(self.itunes_re + '/databases/([0-9]+)/containers/([0-9]+)/items$', parsed_path)
                self.do_GET_container_item_list(md.group(1), md.group(2))
            elif re.match('^/login$', parsed_path):
                self.do_GET_login()
            elif re.match('^/logout$', parsed_path):
                self.do_GET_logout()
            elif re.match('^/update$', parsed_path):
                self.do_GET_update()
            else:
                self.send_error(404)
            return

        def do_HEAD(self):
            self.isHEAD = True
            self.do_GET()

        def do_GET_login(self):
            mlog = do('dmap.loginresponse',
                      [do('dmap.status', 200),
                       do('dmap.sessionid', session_id)])
            self.h(mlog.encode())

        def do_GET_logout(self):
            self.send_response(204)
            self.end_headers()

        def do_GET_server_info(self):
            msrv = do('dmap.serverinforesponse',
                      [do('dmap.status', 200),
                       do('dmap.protocolversion', '2.0'),
                       do('daap.protocolversion', '3.0'),
                       do('dmap.timeoutinterval', 1800),
                       do('dmap.itemname', server_name),
                       do('dmap.loginrequired', 0),
                       do('dmap.authenticationmethod', 0),
                       do('dmap.supportsextensions', 0),
                       do('dmap.supportsindex', 0),
                       do('dmap.supportsbrowse', 0),
                       do('dmap.supportsquery', 0),
                       do('dmap.supportspersistentids', 0),
                       do('dmap.databasescount', 1),
                       #do('dmap.supportsautologout', 0),
                       #do('dmap.supportsupdate', 0),
                       #do('dmap.supportsresolve', 0),
                       ])
            self.h(msrv.encode())

        def do_GET_content_codes(self):
            children = [do('dmap.status', 200)]
            for code in spydaap.daap.dmapCodeTypes.keys():
                (name, dtype) = spydaap.daap.dmapCodeTypes[code]
                d = do('dmap.dictionary',
                       [do('dmap.contentcodesnumber', code),
                        do('dmap.contentcodesname', name),
                        do('dmap.contentcodestype',
                            spydaap.daap.dmapReverseDataTypes[dtype])
                        ])
                children.append(d)
            mccr = do('dmap.contentcodesresponse',
                      children)
            self.h(mccr.encode())

        def do_GET_database_list(self):
            d = do('daap.serverdatabases',
                   [do('dmap.status', 200),
                    do('dmap.updatetype', 0),
                    do('dmap.specifiedtotalcount', 1),
                    do('dmap.returnedcount', 1),
                    do('dmap.listing',
                        [do('dmap.listingitem',
                            [do('dmap.itemid', 1),
                             do('dmap.persistentid', 1),
                             do('dmap.itemname', server_name),
                             do('dmap.itemcount',
                                len(md_cache)),
                             do('dmap.containercount', len(container_cache))])
                         ])
                    ])
            self.h(d.encode())

        def do_GET_item_list(self, database_id):
            def build_item(md):
                return do('dmap.listingitem',
                          [do('dmap.itemkind', 2),
                           do('dmap.containeritemid', md.id),
                           do('dmap.itemid', md.id),
                           md.get_dmap_raw()
                           ])

            def build(f):
                children = [build_item(md) for md in md_cache]
                file_count = len(children)
                d = do('daap.databasesongs',
                       [do('dmap.status', 200),
                        do('dmap.updatetype', 0),
                        do('dmap.specifiedtotalcount', file_count),
                        do('dmap.returnedcount', file_count),
                        do('dmap.listing',
                            children)])
                f.write(d.encode())

            data = cache.get('item_list', build)
            self.h(data)

        def do_GET_update(self):
            mupd = do('dmap.updateresponse',
                      [do('dmap.status', 200),
                       do('dmap.serverrevision', self.daap_server_revision),
                       ])
            self.h(mupd.encode())

        def do_GET_item(self, database, item, format):
            try:
                fn = md_cache.get_item_by_id(item).get_original_filename()
            except IndexError:          # if the track isn't in the DB, we get an exception
                self.send_error(404)    # this can be caused by left overs from previous sessions
                return

            if ('Range' in self.headers):
                rs = self.headers['Range']
                m = re.compile('bytes=([0-9]+)-([0-9]+)?').match(rs)
                (start, end) = m.groups()
                if end is not None:
                    end = int(end)
                else:
                    end = os.stat(fn).st_size
                start = int(start)
                f = spydaap.ContentRangeFile(fn, open(fn), start, end)
                extra_headers = {"Content-Range": "bytes %s-%s/%s" % (str(start), str(end), str(os.stat(fn).st_size))}
                status = 206
            else:
                f = open(fn)
                extra_headers = {}
                status = 200
            # this is ugly, very wrong.
            type = "audio/%s" % (os.path.splitext(fn)[1])
            self.h(f, type=type, status=status, extra_headers=extra_headers)

        def do_GET_container_list(self, database):
            container_do = []
            for i, c in enumerate(container_cache):
                d = [do('dmap.itemid', i + 1),
                     do('dmap.itemcount', len(c)),
                     do('dmap.containeritemid', i + 1),
                     do('dmap.itemname', c.get_name())]
                if c.get_name() == 'Library':  # this should be better
                    d.append(do('daap.baseplaylist', 1))
                else:
                    d.append(do('com.apple.itunes.smart-playlist', 1))
                container_do.append(do('dmap.listingitem', d))
            d = do('daap.databaseplaylists',
                   [do('dmap.status', 200),
                    do('dmap.updatetype', 0),
                    do('dmap.specifiedtotalcount', len(container_do)),
                    do('dmap.returnedcount', len(container_do)),
                    do('dmap.listing',
                        container_do)
                    ])
            self.h(d.encode())

        def do_GET_container_item_list(self, database_id, container_id):
            container = container_cache.get_item_by_id(container_id)
            self.h(container.get_daap_raw())

    return DAAPHandler
