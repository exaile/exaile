PREFIX 		?= /usr/local
PLUGINSDIR 	?= /share/exaile/plugins/

INSTALL_PLUGINS := amazoncovers audioscrobbler gnomemmkeys lastfmdynamic \
	lyricwiki notify shoutcast cd lastfmradio

DIST_PLUGINS := amazoncovers audioscrobbler console gnomemmkeys lastfmcovers \
	lastfmdynamic lyricsfly lyricwiki notify shoutcast cd lastfmradio \
	streamripper tagcovers

dist:	clean
	python dist_plugin.py $(DIST_PLUGINS)

compile:
	python -m compileall .
	python -O -m compileall .

install: compile
	mkdir -p $(DESTDIR)$(PREFIX)$(PLUGINSDIR)
	for plugin in $(INSTALL_PLUGINS); do \
	    cp -r $${plugin} $(DESTDIR)$(PREFIX)$(PLUGINSDIR) ; \
	    done ;

uninstall:
	rm -rf $(PREFIX)$(PLUGINSDIR)*

clean:
	find . -name "*.py[co]" -exec rm -f {} \;
	rm -f *.exz
