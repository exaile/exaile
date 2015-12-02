#!/usr/bin/env python2

import sys

def main():
    sys.argv[1:1] = ['--startgui', '--no-dbus', '--no-hal']
    import exaile
    exaile.main()

if __name__ == '__main__':
    main()
