# Matroska tagger for Exaile
# Copyright (C) 2010  Johannes Sasongko <sasongko@gmail.com>
#
# This program is free software; you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation; either version 2, or (at your option)
# any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program; if not, write to the Free Software
# Foundation, Inc., 51 Franklin Street, Fifth Floor, Boston, MA  02110-1301, USA.
#
#
# The developers of the Exaile media player hereby grant permission
# for non-GPL compatible GStreamer and Exaile plugins to be used and
# distributed together with GStreamer and Exaile. This permission is
# above and beyond the permissions granted by the GPL license by which
# Exaile is covered. If you modify this code, you may extend this
# exception to your version of the code, but you are not obligated to
# do so. If you do not wish to do so, delete this exception statement
# from your version.


from xl.metadata import _base, _matroska


class MkaFormat(_base.BaseFormat):

    others = False  # For now, stick with defined tags only.
    writable = False

    tag_mapping = {
        'album': ('TITLE', 50),
        'album artist': ('ARTIST', 50),
        'artist': ('ARTIST', 30),
        'comment': ('COMMENT', 30),
        'composer': ('COMPOSER', 30),
        'date': ('DATE_RECORDED', 50),
        'discnumber': ('PART_NUMBER', 50),
        'genre': ('GENRE', 30),
        'performer': ('PERFORMER', 30),
        'title': ('TITLE', 30),
        'tracknumber': ('PART_NUMBER', 30),
    }

    def _get_raw(self):
        return self.tags

    def load(self):
        mka = _matroska.parse(self.loc)
        segment = mka['Segment'][0]
        info = segment['Info'][0]
        try:
            timecodescale = info['TimecodeScale'][0]
        except KeyError:
            timecodescale = 1000000
        length = info['Duration'][0] * timecodescale / 1e9
        self.tags = tags = {'__length': length}
        for mkatags in segment['Tags']:
            for mkatag in mkatags['Tag']:
                target = int(mkatag['Targets'][0]['TargetTypevalue'][0])
                for simpletag in mkatag['SimpleTag']:
                    key = (simpletag['TagName'][0], target)
                    try:
                        values = tags[key]
                    except KeyError:
                        values = tags[key] = []
                    values.append(simpletag['TagString'][0])


# vi: et sts=4 sw=4 ts=4
