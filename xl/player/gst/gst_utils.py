# Copyright (C) 2008-2010 Adam Olsen
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


from gi.repository import Gst

from xl.providers import ProviderHandler

import logging

logger = logging.getLogger(__name__)


def element_link_many(*elems):
    for i in range(len(elems) - 1):
        e = elems[i]
        n = elems[i + 1]
        e.link(n)


def disable_video_text(bin):
    # From quod libet: disable all video/text decoding in playbin
    GST_PLAY_FLAG_VIDEO = 1 << 0
    GST_PLAY_FLAG_TEXT = 1 << 2
    flags = bin.get_property("flags")
    flags &= ~(GST_PLAY_FLAG_VIDEO | GST_PLAY_FLAG_TEXT)
    bin.set_property("flags", flags)


class ElementBin(Gst.Bin):
    """
    A bin for easily containing elements

    elements are added to the elements dictionary in the form of
        elements[position] = element
    where position is a value from 0-100 indicating its position
    in the resulting bin, and element is the Gst.Element itself.

    changes made to elements do not apply until setup_elements()
    is called
    """

    def __init__(self, name=None):
        if name:
            Gst.Bin.__init__(self, name=name)
        else:
            Gst.Bin.__init__(self)

        self.elements = {}
        self.added_elems = []
        self.srcpad = None
        self.sinkpad = None
        self.src = None
        self.sink = None

    def setup_elements(self):
        """
        This function should only be called when state is NULL

        :returns: True if there are elements, False otherwise
        """
        name = self.get_name()
        logger.debug("%s: Removing all elements", name)

        if len(self.added_elems) > 0:
            for elem in self.added_elems:
                elem.set_state(Gst.State.NULL)
                self.remove(elem)

        all_elems = sorted(self.elements.items())

        elems = []
        for _unused, e in all_elems:

            # Don't add empty elements!
            if hasattr(e, 'setup_elements'):
                if not e.setup_elements():
                    continue

            elems.append(e)

        self.added_elems = elems

        if len(elems) == 0:
            return False

        for e in elems:
            self.add(e)
            e.sync_state_with_parent()
            logger.debug("%s: Adding %s", name, e.get_name())

        element_link_many(*elems)

        self.srcpad = elems[-1].get_static_pad("src")
        if self.src is not None:
            self.src.set_target(self.srcpad)
        else:
            self.src = Gst.GhostPad.new('src', self.srcpad)
            self.add_pad(self.src)

        self.sinkpad = elems[0].get_static_pad("sink")
        if self.sink is not None:
            self.sink.set_target(self.sinkpad)
        else:
            self.sink = Gst.GhostPad.new('sink', self.sinkpad)
            self.add_pad(self.sink)

        return True


class ProviderBin(ElementBin, ProviderHandler):
    """
    A ProviderBin is a Gst.Bin that adds and removes elements from itself
    using the providers system. Providers should be a subclass of
    Gst.Element and provide the following attributes:
        name  - name to use for this element
        index - priority within the pipeline. range [0-100] integer.
                lower numbers are higher priority. elements must
                choose a unique number.
    """

    def __init__(self, servicename, name=None):
        """
        :param servicename: the Provider name to listen for
        """
        if name is None:
            name = servicename
        ElementBin.__init__(self, name=name)
        ProviderHandler.__init__(self, servicename)

        self.reset_providers()

    def reset_providers(self):
        self.elements = {}
        dups = {}
        for provider in self.get_providers():
            idx = provider.index
            if idx in self.elements:
                dup = dups.setdefault(idx, [self.elements[idx].name])
                dup.append(provider.name)
                while idx in self.elements:
                    idx += 1
            try:
                self.elements[idx] = provider()
            except Exception:
                logger.exception(
                    "Could not create %s element for %s.", provider, self.get_name()
                )

        for k, v in dups.items():
            logger.warning(
                "Audio plugins %s are sharing index %s (may have unpredictable output!)",
                v,
                k,
            )

    def on_provider_added(self, provider):
        self.reset_providers()

    def on_provider_removed(self, provider):
        self.reset_providers()


def parse_stream_tags(track, tag_list):
    """
    Called when a tag is found in a stream.

    :type track:    xl.trax.Track
    :type tag_list: Gst.TagList

    Gst.TagList guarantees that all strings are either ASCII or UTF8
    """

    newsong = False

    keep = [
        'bitrate',
        'duration',
        'track-number',
        'track-count',
        'album-disc-number',
        'album-disc-count',
        'album',
        'artist',
        'genre',
        'comment',
        'title',
        'datetime',
    ]

    # Build a dictionary first
    tags = {}
    for i in range(tag_list.n_tags()):
        k = tag_list.nth_tag_name(i)
        if k not in keep:
            continue

        values = [
            tag_list.get_value_index(k, vi) for vi in range(tag_list.get_tag_size(k))
        ]

        tags[k] = values

    etags = {}

    v = tags.get('bitrate')
    if v:
        etags['__bitrate'] = int(v[0])

    v = tags.get('duration')
    if v:
        etags['__length'] = float(v[0]) / Gst.SECOND

    v = tags.get('track-number')
    if v:
        c = tags.get('track-count')
        if c:
            etags['tracknumber'] = '%d/%d' % (v[0], c[0])
        else:
            etags['tracknumber'] = '%d' % (v[0])

    v = tags.get('album-disc-number')
    if v:
        c = tags.get('album-disc-count')
        if c:
            etags['discnumber'] = '%d/%d' % (v[0], c[0])
        else:
            etags['discnumber'] = '%d' % (v[0])

    v = tags.get('album')
    if v:
        etags['album'] = v

    v = tags.get('artist')
    if v:
        etags['artist'] = v

    v = tags.get('genre')
    if v:
        etags['genre'] = v

    v = tags.get('datetime')
    if v:
        # v[0] is a Gst.DateTime object
        etags['date'] = v[0].to_iso8601_string()

    # if there's a comment, but no album, set album to the comment
    v = tags.get('comment')
    if v and not track.get_tag_raw('album'):
        etags['album'] = v

    v = tags.get('title')
    if v:
        try:
            if track.get_tag_raw('__rawtitle') != v:
                etags['__rawtitle'] = v
                newsong = True
        except AttributeError:
            etags['__rawtitle'] = v
            newsong = True

        if not track.get_tag_raw('artist'):
            title_array = v[0].split(' - ', 1)
            if len(title_array) == 1 or track.get_loc_for_io().lower().endswith(".mp3"):
                etags['title'] = v
            else:
                etags['artist'] = [title_array[0]]
                etags['title'] = [title_array[1]]
        else:
            etags['title'] = v

    track.set_tags(**etags)
    return newsong


# vim: et sts=4 sw=4
