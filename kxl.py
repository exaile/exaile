#!/usr/bin/env python

import os, re

h = os.popen('ps x | grep exaile')
lines = h.readlines()

for line in lines:
    info = re.split(r'\s+', 
        line.strip())
    if len(info) == 6:
        if info[4] == 'python' and info[5] \
            == 'exaile.py':
            os.system('kill -9 %s' % info[0])
