# Copyright (C) 2008 Erik Hetzner
#              2010 Brian Parma

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

import spydaap.parser
from spydaap.daap import do
import logging

logger = logging.getLogger(__name__)


class ExaileParser(spydaap.parser.Parser):
    _string_map = {
        'title': 'dmap.itemname',
        'artist': 'daap.songartist',
        'composer': 'daap.songcomposer',
        'genre': 'daap.songgenre',
        'album': 'daap.songalbum',
    }

    _int_map = {
        'bpm': 'daap.songbeatsperminute',
        # not used by exaile client, and not parsed right anyway (ie: '2010-01-01')
        #        'date': 'daap.songyear', #TODO
        'year': 'daap.songyear',
        'tracknumber': 'daap.songtracknumber',
        'tracktotal': 'daap.songtrackcount',
        'discnumber': 'daap.songdiscnumber',
    }

    def understands(self, filename):
        return True

    #   return self.file_re.match(filename)

    # returns a list in exaile
    def handle_int_tags(self, map, md, daap):
        for k in md.list_tags():
            if k in map:
                try:
                    tn = str(md.get_tag_raw(k)[0])
                    if '/' in tn:
                        num, tot = tn.split('/')
                        if num == '':  # empty tags
                            num = 0
                        daap.append(do(map[k], int(num)))
                        # set total?
                    else:
                        daap.append(do(map[k], int(tn)))
                except Exception:
                    logger.exception(
                        'exception caught parsing tag: %s=%s from %s', k, tn, md
                    )

    # We can't use functions in __init__ because exaile tracks no longer
    # give us access to .tags
    def handle_string_tags(self, map, md, daap):
        for k in md.list_tags():
            if k in map:
                try:
                    tag = [t.encode("utf-8", "replace") for t in md.get_tag_raw(k)]
                    tag = [t for t in tag if t != ""]
                    daap.append(do(map[k], b"/".join(tag)))
                except Exception:
                    logger.exception("error decoding tags")

    def parse(self, trk):
        try:
            # trk = mutagen.File(filename)
            d = []
            if len(trk.list_tags()) > 0:
                if 'title' in trk.list_tags():
                    name = trk.get_tag_raw('title')[0].encode("utf-8", "replace")
                else:
                    name = str(trk)

                self.handle_string_tags(self._string_map, trk, d)
                self.handle_int_tags(self._int_map, trk, d)
            #                self.handle_rating(trk, d)
            else:
                name = str(trk)
            # statinfo = os.stat(filename)

            _len = trk.get_tag_raw('__length')
            if _len is None:  # don't parse songs that don't have length
                return (None, None)

            d.extend(
                [  # do('daap.songsize', trk.get_size()),
                    # do('daap.songdateadded', statinfo.st_ctime),
                    # do('daap.songdatemodified', statinfo.st_ctime),
                    do('daap.songtime', _len * 1000),
                    #                      do('daap.songbitrate', trk.get_tag_raw('__bitrate') / 1000),
                    #                      do('daap.songsamplerate', ogg.info.sample_rate), # todo ??
                    do(
                        'daap.songformat', trk.get_local_path().split('.')[-1]
                    ),  # todo ??
                    do('daap.songdescription', 'Exaile Streaming Audio'),
                ]
            )
            return (d, name)

        except Exception:
            logger.exception('caught exception while processing %s', trk)
            return (None, None)
