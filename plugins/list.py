#!/usr/bin/env python

import os, sys

# - good = works
#   - main = useful
#   - extra = not very useful
# - bad = doesn't work

EXTRA = ['helloworld']
BAD = ['shoutcast']

def scan():
    all = set(f for f in os.listdir('.') if os.path.isdir(f))
    bad = set(BAD)
    good = all - bad
    extra = set(EXTRA)
    main = good - extra
    return locals()

plugins = scan()

def parse(argv):
    if len(argv) == 1:
        return plugins['all']
    return plugins[argv[1]]

if __name__ == '__main__':
    names = list(parse(sys.argv))
    names.sort()
    print(' '.join(names))
