PREFIX = /usr/local
PLUGINSDIR = /share/exaile/plugins/

INSTALL_PLUGINS = audioscrobbler gnomemmkeys lastfmdynamic lastfmcovers \
	lyricwiki notify shoutcast cd lastfmradio ipod massstorage

EXTRA_PLUGINS = amazoncovers console lyricsfly streamripper tagcovers

DIST_PLUGINS = $(INSTALL_PLUGINS) $(EXTRA_PLUGINS)

all: compile

dist: clean
	python dist_plugin.py $(DIST_PLUGINS)

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
	rm -f *.exz
