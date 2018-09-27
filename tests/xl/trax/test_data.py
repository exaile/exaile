import os


def test_mp3_exists(test_tracks):
    assert test_tracks.get('.mp3')


def test_all_tracks(test_track):
    assert os.path.exists(test_track.filename), (
        "%s does not exist" % test_track.filename
    )

    assert test_track.uri.startswith('file:///')


def test_writable_tracks(writeable_track):
    assert os.path.exists(writeable_track.filename), (
        "%s does not exist" % writeable_track.filename
    )

    assert writeable_track.uri.startswith('file:///')
