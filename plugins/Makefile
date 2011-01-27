PREFIX ?= /usr/local
PLUGINSDIR = /share/exaile/plugins/

INSTALL_PLUGINS = `python list.py main`
EXTRA_PLUGINS = `python list.py extra`

DIST_PLUGINS = `python list.py all`

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
