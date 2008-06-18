


dist: clean
	python dist_plugin.py amazoncovers
	python dist_plugin.py audioscrobbler
	python dist_plugin.py gnomemmkeys	
	python dist_plugin.py lastfmcovers
	python dist_plugin.py lastfmdynamic
	python dist_plugin.py lyricsfly
	python dist_plugin.py lyricwiki
	python dist_plugin.py notify
	python dist_plugin.py shoutcast

clean:
	find . -name "*.py[co]" -exec rm -f {} \;
	rm -f *.exz
