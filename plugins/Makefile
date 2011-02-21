PYTHON2_CMD	?= python2
PREFIX		?= /usr/local
PLUGINSDIR	= /share/exaile/plugins/

INSTALL_PLUGINS = `${PYTHON2_CMD} list.py main`
EXTRA_PLUGINS = `${PYTHON2_CMD} list.py extra`

DIST_PLUGINS = `${PYTHON2_CMD} list.py all`

all: compile

dist:
	mkdir -p ../dist/plugins/
	${PYTHON2_CMD} dist_plugin.py --output ../dist/plugins/ ${DIST_PLUGINS}

compile:
	${PYTHON2_CMD} -m compileall -q .
	-${PYTHON2_CMD} -O -m compileall -q .

install:
	mkdir -p ${DESTDIR}${PREFIX}${PLUGINSDIR}
	for plugin in ${INSTALL_PLUGINS}; do \
	    cp -r $${plugin} ${DESTDIR}${PREFIX}${PLUGINSDIR} ; \
	    done ;

extra_install:
	mkdir -p ${DESTDIR}${PREFIX}${PLUGINSDIR}
	for plugin in ${EXTRA_PLUGINS}; do \
	    cp -r $${plugin} ${DESTDIR}${PREFIX}${PLUGINSDIR} ; \
	    done ;

uninstall:
	rm -rf ${PREFIX}${PLUGINSDIR}*

clean:
	find . -name "*.py[co]" -exec rm -f {} \;
