# -*- coding: utf-8  -*-

import os
import unittest
import logging
import random
import string
import types

from gi.repository import GLib
from mox3 import mox
import pytest

import xl.trax.track as track
import xl.settings as settings

LOG = logging.getLogger(__name__)


class Test_MetadataCacher(object):

    TIMEOUT = 2000
    MAX_ENTRIES = 2048

    def setup(self):
        self.mox = mox.Mox()
        self.mc = track._MetadataCacher(self.TIMEOUT, self.MAX_ENTRIES)

    def teardown(self):
        self.mox.UnsetStubs()

    def test_add(self):
        timeout_id = 1
        self.mox.StubOutWithMock(GLib, 'timeout_add_seconds')
        self.mox.StubOutWithMock(GLib, 'source_remove')
        GLib.timeout_add_seconds(
                self.TIMEOUT,
                self.mc._MetadataCacher__cleanup).AndReturn(timeout_id)

        self.mox.ReplayAll()
        self.mc.add('foo', 'bar')
        assert self.mc.get('foo') == 'bar'
        self.mox.VerifyAll()

    def test_double_add(self):
        timeout_id = 1
        self.mox.StubOutWithMock(GLib, 'timeout_add_seconds')
        self.mox.StubOutWithMock(GLib, 'source_remove')
        GLib.timeout_add_seconds(
                mox.IsA(types.IntType),
                mox.IsA(types.MethodType)).AndReturn(timeout_id)

        self.mox.ReplayAll()
        self.mc.add('foo', 'bar')
        assert self.mc.get('foo') == 'bar'
        self.mc.add('foo', 'bar')
        assert self.mc.get('foo') == 'bar'
        self.mox.VerifyAll()

    def test_remove(self):
        timeout_id = 1
        self.mox.StubOutWithMock(GLib, 'timeout_add_seconds')
        GLib.timeout_add_seconds(
                self.TIMEOUT,
                mox.IsA(types.MethodType)).AndReturn(timeout_id)

        self.mox.ReplayAll()
        self.mc.add('foo', 'bar')
        self.mc.remove('foo')
        assert self.mc.get('foo') == None
        self.mox.VerifyAll()

    def test_remove_not_exist(self):
        assert self.mc.remove('foo') == None

def random_str(l=8):
    return ''.join(random.choice(string.ascii_letters) for _ in range(l))

class TestTrack(object):

    def setup(self):
        self.mox = mox.Mox()

    def teardown(self):
        self.mox.UnsetStubs()

    ## Creation
    def test_flyweight(self, test_track):
        """There can only be one object based on a url in args"""
        t1 = track.Track(test_track.filename)
        t2 = track.Track(uri=test_track.uri)
        assert t1 is t2, "%s should be %s" % (repr(t1), repr(t2))

    def test_different_url_not_flyweighted(self, test_tracks):
        t1 = track.Track(test_tracks.get('.mp3').filename)
        t2 = track.Track(test_tracks.get('.ogg').filename)
        assert t1 is not t2, "%s should not be %s" % (repr(t1),
            repr(t2))

    def test_none_url(self):
        with pytest.raises(ValueError):
            track.Track()

    def test_pickles(self):
        tr = track.Track('/foo')
        tr.set_tag_raw('artist', 'bar')
        assert tr._pickles() == {
            '__loc': u'file:///foo',
            'artist': [u'bar']
            }

    def test_unpickles(self):
        tr1 = track.Track(_unpickles={'artist': [u'my_artist'],
            '__loc': u'uri'})
        assert tr1.get_loc_for_io() == u'uri'

    def test_unpickles_flyweight(self):
        tr1 = track.Track(_unpickles={'artist': [u'my_artist'],
            '__loc': u'uri'})
        tr2 = track.Track(_unpickles={'artist': [u'my_artist'],
            '__loc': u'uri'})
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
        assert tr.is_local() == True

    def test_is_local_remote(self):
        """Tests a remote filename -> False"""
        tr = track.Track('http://foo')
        assert tr.is_local() == False

    def test_local_filesize(self, test_track):
        tr = track.Track(test_track.filename)
        assert tr.get_size() == test_track.size

    def test_str(self, test_track):
        loc = test_track.filename
        tr = track.Track(loc)
        self.empty_track_of_tags(tr, ('__loc',))
        trstr = "'Unknown (%s)' from 'Unknown' by 'Unknown'" \
                % os.path.basename(loc)
        assert str(tr) == trstr
        tr.set_tag_raw('artist', 'art')
        tr.set_tag_raw('album', 'alb')
        tr.set_tag_raw('title', 'title')
        assert str(tr) == "'title' from 'alb' by 'art'"

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

    def test_write_tag(self, writeable_track_name):

        artist = random_str()
        tr = track.Track(writeable_track_name)
        tr.set_tag_raw('artist', artist)
        tr.write_tags()

        tr.set_tag_raw('artist', None)
        assert tr.get_tag_raw('artist') == None

        tr.read_tags()

        assert tr.get_tag_raw('artist') == [artist]

    def test_delete_tag(self, writeable_track_name):

        artist = random_str()
        tr = track.Track(writeable_track_name)
        assert tr.get_tag_raw('artist') is not None

        tr.set_tag_raw('artist', None)
        tr.write_tags()

        tr.set_tag_raw('artist', artist)
        tr.read_tags()
        assert tr.get_tag_raw('artist') == None

    def test_write_tag_invalid_format(self):
        tr = track.Track('/tmp/foo.foo')
        assert tr.write_tags() == False

    def test_join_tag_empty(self):
        """Tests get_tag_raw with join=True and an empty tag"""
        tr = track.Track('foo')
        assert tr.get_tag_raw('artist', join=True) == None

    def test_join_tag_one(self):
        """Tests get_tag_raw with join=True and one element in tag"""
        tr = track.Track('foo')
        tr.set_tag_raw('artist', 'foo')
        assert tr.get_tag_raw('artist', join=True) == u'foo'

    def test_join_tag_two(self):
        """Tests get_tag_raw with join=True and one element in tag"""
        tr = track.Track('foo')
        tr.set_tag_raw('artist', [u'foo', u'bar'])
        assert tr.get_tag_raw('artist', join=True) == u'foo / bar'

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
        for tag, val in tags.iteritems():
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
        with pytest.raises(ValueError):
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
        value = u'ßæĳŋœƕǆǉǌǳҥҵ'
        assert track.Track.expand_doubles(value) == \
                u'ssaeijngoehvdzljnjdzngts'

    def test_lower(self):
        value = u'FooBar'
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
        value = u'The Hëllò Wóþλdâ'
        retval = u'The Hello Woþλda The Hëllò Wóþλdâ'
        assert track.Track.strip_marks(value) == retval

    ## Sort tags
    def test_get_sort_tag_no_join(self):
        tr = track.Track('/foo')
        value = u'hello'
        retval = [u'hello hello hello hello']
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
        value = u'The Hëllò Wóþλdâ'
        retval = u'hello woþλda the hëllò wóþλdâ ' \
                 u'The Hello Woþλda The Hëllò Wóþλdâ'
        tr.set_tag_raw('artist', value)
        assert tr.get_tag_sort('artist') == retval

    def test_get_sort_tag_albumsort(self):
        tr = track.Track('/foo')
        value = u'the hello world'
        val_as = u'Foo Bar'
        retval = u'foo bar foo bar Foo Bar Foo Bar'
        tr.set_tag_raw('album', value)
        tr.set_tag_raw('albumsort', val_as)
        assert tr.get_tag_sort('album') == retval

    @unittest.skip("TODO")
    def test_get_sort_tag_compilation_unknown(self):

        tr = track.Track('/foo')
        tr.set_tag_raw('__compilation', 'foo')
        # Does not actually modify anything
        value = u'hello world'
        retval = u' '.join([u'\uffff\uffff\uffff\ufffe'] * 4)
        tr.set_tag_raw('artist', value)
        assert tr.get_tag_sort('artist') == retval

    def test_get_sort_tag_compilation_known(self):
        tr = track.Track('/foo')
        tr.set_tag_raw('__compilation', 'foo')
        value = u'foo bar'
        retval = u'foo bar foo bar foo bar foo bar'
        tr.set_tag_raw('artist', u'hello world')
        tr.set_tag_raw('albumartist', u'albumartist')
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
        val = u'foobar'
        ret = u'foobar foobar foobar foobar'
        tr.set_tag_raw('coverart', u'foobar')
        assert tr.get_tag_sort('coverart') == ret

    ## Display Tags
    def test_get_display_tag_loc(self):
        tr = track.Track('/foo')
        assert tr.get_tag_display('__loc') == '/foo'
        tr = track.Track('http://foo')
        assert tr.get_tag_display('__loc') == 'http://foo'

    @unittest.skip("TODO")
    def test_get_display_tag_compilation(self):
        tr = track.Track('/foo')
        tr.set_tag_raw('__compilation', u'foo')
        assert tr.get_tag_display('artist') == \
                track._VARIOUSARTISTSSTR

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
        assert tr.get_tag_display('__length') == u'360'

    def test_get_display_tag_bitrate(self):
        tr = track.Track('/foo')
        tr.set_tag_raw('__bitrate', 48000)
        assert tr.get_tag_display('__bitrate') == u'48k'

    def test_get_display_tag_bitrate_bitrateless_formate(self, test_tracks):
        td = test_tracks.get('.flac')
        tr = track.Track(td.filename)
        assert tr.get_tag_display('__bitrate') == u''

    def test_get_display_tag_bitrate_bad(self):
        tr = track.Track('/foo')
        tr.set_tag_raw('__bitrate', u'lol')
        assert tr.get_tag_display('__bitrate') == u''

    def test_get_display_tag_numeric_zero(self):
        tr = track.Track('/foo')
        assert tr.get_tag_display('tracknumber') == u''
        assert tr.get_tag_display('discnumber') == u''
        assert tr.get_tag_display('__rating') == u'0'
        assert tr.get_tag_display('__playcount') == u'0'

    def test_get_display_tag_join_true(self):
        tr = track.Track('/foo')
        tr.set_tag_raw('artist', [u'foo', u'bar'])
        assert tr.get_tag_display('artist') == 'foo / bar'

    def test_get_display_tag_join_false(self):
        tr = track.Track('/foo')
        tr.set_tag_raw('artist', [u'foo', u'bar'])
        assert tr.get_tag_display('artist', join=False) == \
                [u'foo', u'bar']

    ## Sort tags
    def test_get_search_tag_loc(self):
        tr = track.Track('/foo')
        assert tr.get_tag_search('__loc') == '__loc=="file:///foo"'

    @unittest.skip("TODO")
    def test_get_search_tag_artist_compilation(self):
        tr = track.Track('/foo')
        tr.set_tag_raw('__compilation', 'foo')
        retval = u'albumartist=="albumartist" ! __compilation==__null__'
        tr.set_tag_raw('artist', u'hello world')
        tr.set_tag_raw('albumartist', u'albumartist')
        tr.set_tag_raw('artistsort', u'foo bar')
        assert tr.get_tag_search('artist') == retval

    def test_get_search_tag_artist(self):
        tr = track.Track('/foo')
        retval = u'artist=="hello world"'
        tr.set_tag_raw('artist', u'hello world')
        assert tr.get_tag_search('artist') == retval

    def test_get_search_tag_artist_none(self):
        tr = track.Track('/foo')
        retval = u'artist==__null__'
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

    def test_get_disk_tag(self, test_tracks):
        td = test_tracks.get('.mp3')
        tr = track.Track(td.filename)
        assert tr.get_tag_disk('artist') == [u'Delerium']

    def test_get_disk_tag_invalid_format(self):
        tr = track.Track('/tmp/foo.bah')
        assert tr.get_tag_disk('artist') == None

    def test_list_disk_tag(self, test_tracks):
        td = test_tracks.get('.ogg')
        tr = track.Track(td.filename)
        assert set(tr.list_tags_disk()) == \
                        {'album', 'cover', 'tracknumber', 'artist', 'title'}

    def test_list_disk_tag_invalid_format(self):
        tr_name = '/tmp/foo.foo'
        tr = track.Track(tr_name)
        assert tr.list_tags_disk() == None

