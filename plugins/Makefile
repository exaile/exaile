PREFIX ?= /usr/local
PLUGINSDIR = /share/exaile/plugins/

INSTALL_PLUGINS = alarmclock \
		  amazoncovers \
		  audioscrobbler \
		  bookmarks \
		  cd \
		  desktopcover \
		  gnomemmkeys \
		  ipod \
		  lastfmdynamic \
		  lastfmcovers \
		  lastfmradio \
		  lyricsfly \
		  lyricwiki \
		  massstorage \
		  moodbar \
		  mpris \
		  multialarmclock \
		  notify \
		  replaygain \
		  screensaverpause \
		  shoutcast \
		  streamripper \
		  tagcovers 

EXTRA_PLUGINS = console \
	       	ipconsole \
	       	helloworld

DIST_PLUGINS = $(INSTALL_PLUGINS) $(EXTRA_PLUGINS)

all: compile

dist:
	mkdir -p ../dist/plugins/
	python dist_plugin.py --output ../dist/plugins/ $(DIST_PLUGINS)

compile:
	python -m compileall -q .
	-python -O -m compileall -q .

install:
	mkdir -p $(DESTDIR)$(PREFIX)$(PLUGINSDIR)
	for plugin in $(INSTALL_PLUGINS); do \
	    cp -r $${plugin} $(DESTDIR)$(PREFIX)$(PLUGINSDIR) ; \
	    done ;

extra_install:
	mkdir -p $(DESTDIR)$(PREFIX)$(PLUGINSDIR)
	for plugin in $(EXTRA_PLUGINS); do \
	    cp -r $${plugin} $(DESTDIR)$(PREFIX)$(PLUGINSDIR) ; \
	    done ;

uninstall:
	rm -rf $(PREFIX)$(PLUGINSDIR)*

clean:
	find . -name "*.py[co]" -exec rm -f {} \;
