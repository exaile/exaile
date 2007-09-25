#!/usr/bin/env python

# Copyright (C) 2007 Roman Koller
#
# This program is free software; you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation; either version 2, or (at your option)
# any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program; if not, write to the Free Software
# Foundation, Inc., 675 Mass Ave, Cambridge, MA 02139, USA.

#
# Title:				Exaile-cover-mover
# Description:		This program moves the covers fetched by Exaile directly to your music library.
# Requirements: 	- Exaile closed
# Known Bugs:		- Not able to handle files with non-Unicode characters
# Author: 			Roman Koller
# Date: 				11-09-2007
#

# imports
from pysqlite2 import dbapi2 as sqlite
import shutil, os.path, os

# the filename for covers
coverfile = "cover.jpg"

# let's go
exailepath = os.path.join(os.path.expanduser('~'), '.exaile')
dbfile = os.path.join(exailepath, 'music.db')
print "Opening database %s..." % dbfile,
exit

# open exaile database
db = sqlite.connect(dbfile)
cursor = db.cursor()

print "Done.\nGetting all albums with amazon cover...",
cursor.execute('SELECT a.image, p.name, a.id FROM tracks AS t, albums AS a, paths AS p WHERE t.path = p.id AND a.id = t.album AND a.image != \'\' AND a.image != \'nocover\' ORDER BY p.name') # LIMIT 200
print "Done.\nGetting paths...",

# put all paths and information to array paths
paths = []
for i in cursor:
	index = i[1].rfind(os.sep)
	# only once per path
	if [i[1][:index], i[0], i[2]] not in paths:
		paths.append([i[1][:index], i[0], i[2]])
		
print "Done.\nMoving %i covers..." % (len(paths))

# move picture to album folder
for i in paths:
	print "\t%s..." % i[0],
	try:
		shutil.move(os.path.join(exailepath, 'covers', str(i[1])), os.path.join(str(i[0]), coverfile))
	except IOError, (errno, strerror):
		if errno == 2:
			print "Database is not synchronised with your filesystem. There's already a cover. Skipping."
		else:
			print "IOError %i: %s" % (errno, strerror)
		continue
	except UnicodeEncodeError:
		print "Unfortunately, Python is not yet ready to deal with filenames that are not Unicode. Skipping."
		continue
	print "Done."
	
print "All covers moved."

again = True
while again:
	user_input = raw_input("Should all other covers be removed, too (and get lost) (y=yes*, n=no)? ").strip().lower()

	if not user_input or user_input == 'y':
		# update database, remove all amazon album covers
		print "Database update... ",
		try:
			cursor.execute('UPDATE albums SET image = \'\', amazon_image = 0') 
		except sqlite.OperationalError:
			print "Database is locked. Close Exaile and try again."
		print "Done.\nRemoving fetched but unused covers from filesystem...",
		
		# remove fetched but unused covers from filesystem
		shutil.rmtree(os.path.join(exailepath, 'covers'))
		os.mkdir(os.path.join(exailepath, 'covers'))
		print "Done."
		
		again = False
	
	elif user_input == 'n':
		print "Skipped.\nRemoving only moved covers from database..."
		for i in paths:
			try:
				cursor.execute("UPDATE albums SET image = '', amazon_image = 0 WHERE id = '%i'" %i[2])
			except sqlite.OperationalError:
				print "Database is locked. Close Exaile and try again."
		
		again = False


# submit db changes, close connection
db.commit()
cursor.close()	

