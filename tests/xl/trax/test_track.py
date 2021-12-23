# -*- coding: utf-8  -*-

import itertools
import os
import unittest
import logging
import random
import string
import types
from unittest.mock import Mock, patch

from gi.repository import GLib
import pytest

from xl.metadata import CoverImage
import xl.trax.track as track
import xl.settings as settings

LOG = logging.getLogger(__name__)


class Test_MetadataCacher:

    TIMEOUT = 2000
    MAX_ENTRIES = 2

    def setup(self):
        self.mc: track._MetadataCacher[str, str] = track._MetadataCacher(
            self.TIMEOUT, self.MAX_ENTRIES
        )
        self.patched_glib = patch.multiple(
            GLib, timeout_add_seconds=Mock(), source_remove=Mock()
        )

    def test_add(self):
        with self.patched_glib:
            self.mc.add('foo', 'bar')
            assert self.mc.get('foo') == 'bar'
            GLib.timeout_add_seconds.assert_called_once_with(
                self.TIMEOUT, self.mc._MetadataCacher__cleanup
            )

    def test_double_add(self):
        with self.patched_glib:
            self.mc.add('foo', 'bar')
            assert self.mc.get('foo') == 'bar'
            self.mc.add('foo', 'bar')
            assert self.mc.get('foo') == 'bar'
            GLib.timeout_add_seconds.assert_called_once_with(
                self.TIMEOUT, self.mc._MetadataCacher__cleanup
            )

    def test_overflow(self):
        """
        When the cache overflows, the least-recently used entry is removed
        """
        assert self.MAX_ENTRIES == 2
        increasing_time = patch('time.time', Mock(side_effect=itertools.count(1)))
        with self.patched_glib, increasing_time:
            self.mc.add('k1', 'v1')  # [entry1(time=1)]
            self.mc.add('k2', 'v2')  # [entry1(time=1), entry2(time=2)]
            assert self.mc.get('k2')  # [entry1(time=1), entry2(time=3)]
            assert self.mc.get('k1')  # [entry1(time=4), entry2(time=3)]
            # Adding another entry should remove entry2 because it has the
            # smallest time value
            self.mc.add('k3', 'v3')  # [entry1(time=4), entry3(time=5)]
            assert not self.mc.get('k2')
            assert self.mc.get('k1')
            assert self.mc.get('k3')

    def test_remove(self):
        with self.patched_glib:
            self.mc.add('foo', 'bar')
            self.mc.remove('foo')
            assert self.mc.get('foo') is None

    def test_remove_not_exist(self):
        assert self.mc.remove('foo') is None


def random_str(l=8):
    return ''.join(random.choice(string.ascii_letters) for _ in range(l))


class TestTrack:
    def verify_tags_exist(self, tr, test_track, deleted=None):
        internal_tags = {'__length', '__modified', '__basedir', '__basename', '__loc'}
        if test_track.ext not in ['aac', 'spx']:
            internal_tags.add('__bitrate')

        disk_tags = {'album', 'tracknumber', 'artist', 'title'}
        normal_tags = internal_tags | disk_tags

        if test_track.has_cover:
            disk_tags.add('cover')

        if deleted:
            normal_tags.discard(deleted)
            disk_tags.remove(deleted)

        # check non-disk tag list
        assert set(tr.list_tags()) == normal_tags

        # check disk tag list
        assert set(tr.list_tags_disk()) == disk_tags

    ## Creation
    def test_flyweight(self, test_track):
        """There can only be one object based on a url in args"""
        t1 = track.Track(test_track.filename)
        t2 = track.Track(uri=test_track.uri)
        assert t1 is t2, "%s should be %s" % (repr(t1), repr(t2))

    def test_different_url_not_flyweighted(self, test_tracks):
        t1 = track.Track(test_tracks.get('.mp3').filename)
        t2 = track.Track(test_tracks.get('.ogg').filename)
        assert t1 is not t2, "%s should not be %s" % (repr(t1), repr(t2))

    def test_none_url(self):
        with pytest.raises(ValueError):
            track.Track()

    def test_pickles(self):
        tr = track.Track('/foo')
        tr.set_tag_raw('artist', 'bar')
        assert tr._pickles() == {'__loc': 'file:///foo', 'artist': ['bar']}

    def test_unpickles(self):
        tr1 = track.Track(_unpickles={'artist': ['my_artist'], '__loc': 'uri'})
        assert tr1.get_loc_for_io() == 'uri'

    def test_unpickles_flyweight(self):
        tr1 = track.Track(_unpickles={'artist': ['my_artist'], '__loc': 'uri'})
        tr2 = track.Track(_unpickles={'artist': ['my_artist'], '__loc': 'uri'})
        assert tr1 is tr2

    def test_takes_nonurl(self, test_track):
        tr = track.Track(test_track.filename)

        assert tr.get_local_path()
        assert tr.exists()

    def test_takes_url(self, test_track):
        tr = track.Track(test_track.uri)

        assert tr.get_local_path()
        assert tr.exists()

    ## Information
    def test_local_type(self, test_track):
        tr = track.Track(test_track.filename)
        assert tr.get_type() == 'file'

    def test_is_local_local(self):
        """Tests a local filename -> True"""
        tr = track.Track('foo')
        assert tr.is_local() is True

    def test_is_local_remote(self):
        """Tests a remote filename -> False"""
        tr = track.Track('http://foo')
        assert tr.is_local() is False

    def test_local_filesize(self, test_track):
        tr = track.Track(test_track.filename)
        assert tr.get_size() == test_track.size

    def test_str(self, test_track):
        loc = test_track.filename
        tr = track.Track(loc)
        self.empty_track_of_tags(tr, ('__loc',))
        trstr = "<Track 'Unknown (%s)' by '' from ''>" % os.path.basename(loc)
        assert str(tr) == trstr
        tr.set_tag_raw('artist', 'art')
        tr.set_tag_raw('album', 'alb')
        tr.set_tag_raw('title', 'title')
        assert str(tr) == "<Track 'title' by 'art' from 'alb'>"

    def test_read_tags_no_perms(self, test_track_fp):

        tr = track.Track(test_track_fp.name)
        # first, ensure that we can actually read the tags to begin with
        assert tr.read_tags()

        os.chmod(test_track_fp.name, 0o000)

        # opening the file should fail...
        with pytest.raises(IOError):
            with open(test_track_fp.name, 'rb'):
                pass

        # second, ensure that we can no longer read them
        assert not tr.read_tags()

    def test_write_tags_no_perms(self, test_track_fp):

        os.chmod(test_track_fp.name, 0o444)

        tr = track.Track(test_track_fp.name)
        tr.set_tag_raw('artist', random_str())
        assert not tr.write_tags()

    def test_write_tag(self, writeable_track, writeable_track_name):

        artist = random_str()
        tr = track.Track(writeable_track_name)
        tr.set_tag_raw('artist', artist)
        assert tr.write_tags() is not False
        assert tr.get_tag_raw('artist') == [artist]

        # if tag was changed, ensure it gets overridden by reading tags from file
        tr.set_tag_raw('artist', None)
        assert tr.get_tag_raw('artist') is None

        assert tr.read_tags() is not False
        assert tr.get_tag_raw('artist') == [artist]

        self.verify_tags_exist(tr, writeable_track)

    def test_delete_tag(self, writeable_track, writeable_track_name):

        artist = random_str()
        tr = track.Track(writeable_track_name)
        assert tr.get_tag_raw('artist') is not None

        tr.set_tag_raw('artist', None)
        assert tr.write_tags() is not False
        assert tr.get_tag_raw('artist') is None

        # if tag was deleted, ensure it gets overridden by reading tags from file
        tr.set_tag_raw('artist', artist)
        assert tr.get_tag_raw('artist') == [artist]

        assert tr.read_tags() is not False
        assert tr.get_tag_raw('artist') is None

        self.verify_tags_exist(tr, writeable_track, deleted='artist')

    def test_delete_missing_tag(self, writeable_track, writeable_track_name):
        tr = track.Track(writeable_track_name)
        assert tr.get_tag_raw('genre') is None
        tr.set_tag_raw('genre', None)
        assert tr.get_tag_raw('genre') is None

        self.verify_tags_exist(tr, writeable_track)

        # this actually writes it to disk
        assert tr.write_tags() is not False

        # make sure another read works
        assert tr.read_tags() is not False

        self.verify_tags_exist(tr, writeable_track)

    def test_write_delete_cover(self, writeable_track, writeable_track_name):
        if not writeable_track.has_cover:
            return

        if writeable_track.ext in ['aac', 'mp4']:
            from mutagen.mp4 import MP4Cover

            newcover = CoverImage(
                None, None, 'image/jpeg', MP4Cover(random_str().encode('utf-8'))
            )
        else:
            newcover = CoverImage(
                3, 'cover', 'image/jpeg', random_str().encode('utf-8')
            )

        tr = track.Track(writeable_track_name)
        assert tr.get_tag_raw('cover') is None
        assert tr.get_tag_disk('cover') is not None

        # Can we delete a cover?
        tr.set_tag_disk('cover', None)
        assert tr.write_tags() is not False

        self.verify_tags_exist(tr, writeable_track, deleted='cover')

        # Can we write a new cover?
        tr.set_tag_disk('cover', newcover)
        assert tr.get_tag_raw('cover') is None
        assert tr.get_tag_disk('cover') == [newcover]

        # reading the tags shouldn't change anything, since we're reading from disk
        assert tr.read_tags() is not False
        assert tr.get_tag_raw('cover') is None
        assert tr.get_tag_disk('cover') == [newcover]

        self.verify_tags_exist(tr, writeable_track)

    def test_write_tag_invalid_format(self):
        tr = track.Track('/tmp/foo.foo')
        assert tr.write_tags() is False

    def test_join_tag_empty(self):
        """Tests get_tag_raw with join=True and an empty tag"""
        tr = track.Track('foo')
        assert tr.get_tag_raw('artist', join=True) is None

    def test_join_tag_one(self):
        """Tests get_tag_raw with join=True and one element in tag"""
        tr = track.Track('foo')
        tr.set_tag_raw('artist', 'foo')
        assert tr.get_tag_raw('artist', join=True) == 'foo'

    def test_join_tag_two(self):
        """Tests get_tag_raw with join=True and one element in tag"""
        tr = track.Track('foo')
        tr.set_tag_raw('artist', ['foo', 'bar'])
        assert tr.get_tag_raw('artist', join=True) == 'foo / bar'

    def empty_track_of_tags(self, track, exclude=None):
        """Removes all the tags from a track"""
        for tag in track.list_tags():
            if exclude is not None and tag in exclude:
                continue
            track.set_tag_raw(tag, None)

    def test_list_tags(self, test_track):
        tr = track.Track(test_track.filename)
        tags = {'artist': 'foo', 'album': 'bar', '__loc': test_track.filename}
        self.empty_track_of_tags(tr, tags)
        for tag, val in tags.items():
            tr.set_tag_raw(tag, val)
        assert set(tr.list_tags()) == {'album', '__loc', 'artist', '__basename'}

    def test_rating_empty(self):
        """Test get_rating when no rating has been set"""
        tr = track.Track('/foo')
        assert tr.get_rating() == 0

    def test_set_rating(self):
        tr = track.Track('/foo')
        tr.set_rating(2)
        assert tr.get_rating() == 2

    def test_set_rating_invalid(self):
        tr = track.Track('/bar')
        with pytest.raises(TypeError):
            tr.set_rating('foo')

    ## Tag Getting helper methods
    def test_split_numerical_none(self):
        assert track.Track.split_numerical(None) == (None, 0)

    def test_split_numerical_str(self):
        fn = track.Track.split_numerical
        assert fn('12/15') == (12, 15)
        assert fn('foo/15') == (None, 15)
        assert fn('12/foo') == (12, 0)
        assert fn('12/15/2009') == (12, 15)

    def test_split_numerical_list(self):
        fn = track.Track.split_numerical
        assert fn(['12/15']) == (12, 15)
        assert fn(['foo/15']) == (None, 15)
        assert fn(['12/foo']) == (12, 0)
        assert fn(['12/15/2009']) == (12, 15)

    def test_strip_leading(self):
        # Strips whitespace if it's an empty string
        value = " `~!@#$%^&*()_+-={}|[]\\\";'<>?,./"
        retvalue = "`~!@#$%^&*()_+-={}|[]\\\";'<>?,./"
        assert track.Track.strip_leading(value) == retvalue
        assert track.Track.strip_leading(value + "foo") == "foo"

    def test_cutter(self):
        value = 'the a foo'
        assert track.Track.the_cutter(value) == 'a foo'

    def test_expand_doubles(self):
        value = 'ßæĳŋœƕǆǉǌǳҥҵ'
        assert track.Track.expand_doubles(value) == 'ssaeijngoehvdzljnjdzngts'

    def test_lower(self):
        value = 'FooBar'
        assert track.Track.lower(value) == 'foobar FooBar'

    def test_cuts_cb(self):
        value = []
        settings.set_option('collection/strip_list', value)
        track.Track._the_cuts_cb(None, None, 'collection/strip_list')
        assert track.Track._Track__the_cuts == value

        value = ['the', 'foo']
        settings.set_option('collection/strip_list', value)
        track.Track._the_cuts_cb(None, None, 'collection/strip_list')
        assert track.Track._Track__the_cuts == value

    def test_strip_marks(self):
        value = 'The Hëllò Wóþλdâ'
        retval = 'The Hello Woþλda The Hëllò Wóþλdâ'
        assert track.Track.strip_marks(value) == retval

    ## Sort tags
    def test_get_sort_tag_no_join(self):
        tr = track.Track('/foo')
        value = 'hello'
        retval = ['hello hello hello hello']
        tr.set_tag_raw('artist', value)
        assert tr.get_tag_sort('artist', join=False) == retval

    def test_get_sort_tag_discnumber(self):
        tr = track.Track('/foo')
        value = '12/15'
        retval = 12
        tr.set_tag_raw('discnumber', value)
        assert tr.get_tag_sort('discnumber') == retval

    def test_get_sort_tag_tracknumber(self):
        tr = track.Track('/foo')

        value = '12/15'
        retval = 12
        tr.set_tag_raw('tracknumber', value)
        assert tr.get_tag_sort('tracknumber') == retval

    def test_get_sort_tag_artist(self):
        tr = track.Track('/foo')
        value = 'The Hëllò Wóþλdâ'
        retval = 'hello woþλda the hëllò wóþλdâ ' 'The Hello Woþλda The Hëllò Wóþλdâ'
        tr.set_tag_raw('artist', value)
        assert tr.get_tag_sort('artist') == retval

    def test_get_sort_tag_albumsort(self):
        tr = track.Track('/foo')
        value = 'the hello world'
        val_as = 'Foo Bar'
        retval = 'foo bar foo bar Foo Bar Foo Bar'
        tr.set_tag_raw('album', value)
        tr.set_tag_raw('albumsort', val_as)
        assert tr.get_tag_sort('album') == retval

    @unittest.skip("TODO")
    def test_get_sort_tag_compilation_unknown(self):

        tr = track.Track('/foo')
        tr.set_tag_raw('__compilation', 'foo')
        # Does not actually modify anything
        value = 'hello world'
        retval = ' '.join(['\uffff\uffff\uffff\ufffe'] * 4)
        tr.set_tag_raw('artist', value)
        assert tr.get_tag_sort('artist') == retval

    def test_get_sort_tag_compilation_known(self):
        tr = track.Track('/foo')
        tr.set_tag_raw('__compilation', 'foo')
        value = 'foo bar'
        retval = 'foo bar foo bar foo bar foo bar'
        tr.set_tag_raw('artist', 'hello world')
        tr.set_tag_raw('albumartist', 'albumartist')
        tr.set_tag_raw('artistsort', value)
        assert tr.get_tag_sort('artist') == retval

    def test_get_sort_tag_length(self):
        tr = track.Track('/foo')
        tr.set_tag_raw('__length', 36)
        assert tr.get_tag_sort('__length') == 36

    def test_get_sort_tag_playcount(self):
        tr = track.Track('/foo')
        tr.set_tag_raw('__playcount', 36)
        assert tr.get_tag_sort('__playcount') == 36

    def test_get_sort_tag_other(self):
        tr = track.Track('/foo')
        val = 'foobar'
        ret = 'foobar foobar foobar foobar'
        tr.set_tag_raw('coverart', val)
        assert tr.get_tag_sort('coverart') == ret

    ## Display Tags
    def test_get_display_tag_loc(self):
        import sys

        if sys.platform == 'win32':
            tr = track.Track('C:\\foo')
            assert tr.get_tag_display('__loc') == 'C:\\foo'
        else:
            tr = track.Track('/foo')
            assert tr.get_tag_display('__loc') == '/foo'
        tr = track.Track('http://foo/bar')
        assert tr.get_tag_display('__loc') == 'http://foo/bar'

    @unittest.skip("TODO")
    def test_get_display_tag_compilation(self):
        tr = track.Track('/foo')
        tr.set_tag_raw('__compilation', 'foo')
        assert tr.get_tag_display('artist') == track._VARIOUSARTISTSSTR

    def test_get_display_tag_discnumber(self):
        tr = track.Track('/foo')
        value = '12/15'
        retval = '12'
        tr.set_tag_raw('discnumber', value)
        assert tr.get_tag_display('discnumber') == retval

    def test_get_display_tag_tracknumber(self):
        tr = track.Track('/foo')
        value = '12/15'
        retval = '12'
        tr.set_tag_raw('tracknumber', value)
        assert tr.get_tag_display('tracknumber') == retval

    def test_get_display_tag_length(self):
        tr = track.Track('/foo')
        tr.set_tag_raw('__length', 360)
        assert tr.get_tag_display('__length') == '360'

    def test_get_display_tag_bitrate(self):
        tr = track.Track('/foo')
        tr.set_tag_raw('__bitrate', 48000)
        assert tr.get_tag_display('__bitrate') == '48k'

    def test_get_display_tag_bitrate_bitrateless_formate(self, test_tracks):
        td = test_tracks.get('.flac')
        tr = track.Track(td.filename)
        assert tr.get_tag_display('__bitrate') == ''

    def test_get_display_tag_bitrate_bad(self):
        tr = track.Track('/foo')
        tr.set_tag_raw('__bitrate', 'lol')
        assert tr.get_tag_display('__bitrate') == ''

    def test_get_display_tag_numeric_zero(self):
        tr = track.Track('/foo')
        assert tr.get_tag_display('tracknumber') == ''
        assert tr.get_tag_display('discnumber') == ''
        assert tr.get_tag_display('__rating') == '0'
        assert tr.get_tag_display('__playcount') == '0'

    def test_get_display_tag_join_true(self):
        tr = track.Track('/foo')
        tr.set_tag_raw('artist', ['foo', 'bar'])
        assert tr.get_tag_display('artist') == 'foo / bar'

    def test_get_display_tag_join_false(self):
        tr = track.Track('/foo')
        tr.set_tag_raw('artist', ['foo', 'bar'])
        assert tr.get_tag_display('artist', join=False) == ['foo', 'bar']

    ## Sort tags
    def test_get_search_tag_loc(self):
        tr = track.Track('/foo')
        assert tr.get_tag_search('__loc') == '__loc=="file:///foo"'

    @unittest.skip("TODO")
    def test_get_search_tag_artist_compilation(self):
        tr = track.Track('/foo')
        tr.set_tag_raw('__compilation', 'foo')
        retval = 'albumartist=="albumartist" ! __compilation==__null__'
        tr.set_tag_raw('artist', 'hello world')
        tr.set_tag_raw('albumartist', 'albumartist')
        tr.set_tag_raw('artistsort', 'foo bar')
        assert tr.get_tag_search('artist') == retval

    def test_get_search_tag_artist(self):
        tr = track.Track('/foo')
        retval = 'artist=="hello world"'
        tr.set_tag_raw('artist', 'hello world')
        assert tr.get_tag_search('artist') == retval

    def test_get_search_tag_artist_none(self):
        tr = track.Track('/foo')
        retval = 'artist==__null__'
        assert tr.get_tag_search('artist') == retval

    def test_get_search_tag_discnumber(self):
        tr = track.Track('/foo')
        value = '12/15'
        retval = 'discnumber=="12"'
        tr.set_tag_raw('discnumber', value)
        assert tr.get_tag_search('discnumber') == retval

    def test_get_search_tag_tracknumber(self):
        tr = track.Track('/foo')
        value = '12/15'
        retval = 'tracknumber=="12"'
        tr.set_tag_raw('tracknumber', value)
        assert tr.get_tag_search('tracknumber') == retval

    def test_get_search_tag_length(self):
        tr = track.Track('/foo')
        tr.set_tag_raw('__length', 36)
        assert tr.get_tag_search('__length') == '__length=="36"'

    def test_get_search_tag_bitrate(self):
        tr = track.Track('/foo')
        tr.set_tag_raw('__bitrate', 48000)
        assert tr.get_tag_search('__bitrate') == '__bitrate=="48k" __bitrate=="48000"'

    def test_get_disk_tag_invalid_format(self):
        tr = track.Track('/tmp/foo.bah')
        assert tr.get_tag_disk('artist') is None

    def test_list_disk_tag_invalid_format(self):
        tr_name = '/tmp/foo.foo'
        tr = track.Track(tr_name)
        assert tr.list_tags_disk() is None

    def test_read_real_tracks(self, test_track):
        if not test_track.has_tags:
            return

        tr = track.Track(test_track.filename)

        # raw tags
        assert tr.get_tag_raw('album') == ['Chimera']
        assert tr.get_tag_raw('artist') == ['Delerium']
        assert tr.get_tag_raw('title') == ['Truly']
        assert tr.get_tag_raw('tracknumber') in [['5'], ['5/0']]

        # disk tags should be the same
        assert tr.get_tag_disk('album') == ['Chimera']
        assert tr.get_tag_disk('artist') == ['Delerium']
        assert tr.get_tag_disk('title') == ['Truly']
        assert tr.get_tag_disk('tracknumber') in [['5'], ['5/0']]

        self.verify_tags_exist(tr, test_track)
