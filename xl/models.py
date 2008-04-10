import sqlobject, os, datetime
from sqlite3 import dbapi2 as sqlite

class Track(sqlobject.SQLObject):
    """
        Represents the track table, each track is stored here
    """

    path = sqlobject.StringCol()
    title = sqlobject.StringCol()
    length = sqlobject.IntCol(default=0)
    track = sqlobject.IntCol(default=-1)
    disc = sqlobject.IntCol(default=-1)
    bitrate = sqlobject.IntCol(default=0)
    size = sqlobject.IntCol(default=0)
    modified = sqlobject.IntCol(default=0)
    tags = sqlobject.StringCol(default=None)
    plays = sqlobject.IntCol(default=0)
    rating = sqlobject.IntCol(default=0)
    blacklisted = sqlobject.BoolCol(default=False)
    time_added = sqlobject.TimestampCol(default=datetime.datetime.now())
    last_played = sqlobject.TimestampCol(default=datetime.datetime.now())
    artist = sqlobject.ForeignKey('Artist')
    album = sqlobject.ForeignKey('Album')

class Album(sqlobject.SQLObject):
    """
        Represents albums table
    """

    name = sqlobject.StringCol()
    image_path = sqlobject.StringCol(default=None)
    small_image_path = sqlobject.StringCol(default=None)
    tracks = sqlobject.MultipleJoin('Track')
    artist = sqlobject.ForeignKey('Artist')

class Artist(sqlobject.SQLObject):
    """ 
        Represents artists table
    """

    name = sqlobject.StringCol()
    tracks = sqlobject.MultipleJoin('Track')
    albums = sqlobject.MultipleJoin('Album')

def test_function():
    file = os.path.abspath('data.db')
    con = sqlobject.connectionForURI('sqlite:' + file)
    con._debug = True
    sqlobject.sqlhub.processConnection = con

    Track.createTable()
    Album.createTable()
    Artist.createTable()

    artist = Artist(name='Metallica')
    album = Album(name='Black Album', artist=artist)


    track = Track(path='woot.mp3', title="Nothing Else Matters", album=album,
        artist=artist)

# test function
if __name__ == "__main__":
    test_function()
