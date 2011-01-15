#!/usr/bin/env python

import os
files = []
for file in os.listdir('.'):
    if os.path.isdir(file):
        files.append(file)

print (' '.join(files))
