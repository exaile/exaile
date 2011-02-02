PYTHON_EXEC	?= python2
PREFIX		?= /usr/local
PLUGINSDIR	= /share/exaile/plugins/

INSTALL_PLUGINS = `$(PYTHON_EXEC) list.py main`
EXTRA_PLUGINS = `$(PYTHON_EXEC) list.py extra`

DIST_PLUGINS = `$(PYTHON_EXEC) list.py all`

all: compile

dist:
	mkdir -p ../dist/plugins/
	$(PYTHON_EXEC) dist_plugin.py --output ../dist/plugins/ $(DIST_PLUGINS)

compile:
	$(PYTHON_EXEC) -m compileall -q .
	-$(PYTHON_EXEC) -O -m compileall -q .

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
