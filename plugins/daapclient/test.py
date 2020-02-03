# This file contains some code to test the DAAPClient as stand-alone application.

import sys
import logging

from .client import DAAPClient

log = logging.getLogger(__name__)


def main():
    connection = DAAPClient()

    if len(sys.argv) > 1:
        host = sys.argv[1]
    else:
        host = "localhost"
    if len(sys.argv) > 2:
        port = sys.argv[2]
    else:
        port = 3689

    logging.basicConfig(
        level=logging.DEBUG, format='%(asctime)s %(levelname)s %(message)s'
    )

    try:
        # do everything in a big try, so we can disconnect at the end
        connection.connect(host, port)

        # auth isn't supported yet. Just log in
        session = connection.login()

        library = session.library()
        log.debug("Library name is `%r`", library.name)

        tracks = library.tracks()

        # demo - save the first track to disk
        # print("Saving %s by %s to disk as 'track.mp3'"%(tracks[0].name, tracks[0].artist))
        # tracks[0].save("track.mp3")
        if len(tracks) > 0:
            tracks[0].atom.printTree()
        else:
            print('No Tracks')
        session.update()
        print(session.revision)

    finally:
        # this here, so we logout even if there's an error somewhere,
        # or itunes will eventually refuse more connections.
        print("--------------")
        try:
            session.logout()
        except Exception:
            pass


if __name__ == '__main__':
    main()
