#!/usr/bin/env python3

import sys


def main():
    sys.argv[1:1] = ['--startgui', '--no-dbus', '--no-hal']
    import exaile

    exaile.main()


if __name__ == '__main__':
    main()
