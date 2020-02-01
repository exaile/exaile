PYTHON3_CMD	?= python3
PREFIX		?= /usr/local
PLUGINSDIR	= /share/exaile/plugins/

INSTALL_PLUGINS = `${PYTHON3_CMD} list.py main`
EXTRA_PLUGINS = `${PYTHON3_CMD} list.py extra`

DIST_PLUGINS = `${PYTHON3_CMD} list.py all`

all: compile

dist:
	mkdir -p ../dist/plugins/ && \
	${PYTHON3_CMD} dist_plugin.py --output ../dist/plugins/ ${DIST_PLUGINS}

compile:
	${PYTHON3_CMD} -m compileall -q .
	-${PYTHON3_CMD} -O -m compileall -q .

install:
	install -d -m 755 ${DESTDIR}${PREFIX}${PLUGINSDIR}
	for plugin in ${INSTALL_PLUGINS}; do \
		install -d -m 755 ${DESTDIR}${PREFIX}${PLUGINSDIR}$$plugin && \
		for f in `find $$plugin -type f` ; do \
			install -d -m 755 `echo ${DESTDIR}${PREFIX}${PLUGINSDIR}$$f | \
				xargs dirname` && \
			install -m 644 $$f ${DESTDIR}${PREFIX}${PLUGINSDIR}$$f ; \
		done ; \
    done

extra_install:
	install -d -m 755 ${DESTDIR}${PREFIX}${PLUGINSDIR}
	for plugin in ${EXTRA_PLUGINS}; do \
		install -d -m 755 ${DESTDIR}${PREFIX}${PLUGINSDIR}$$plugin && \
		for f in `find $$plugin -type f` ; do \
			install -d -m 755 `echo ${DESTDIR}${PREFIX}${PLUGINSDIR}$$f | \
				xargs dirname` && \
			install -m 644 $$f ${DESTDIR}${PREFIX}${PLUGINSDIR}$$f ; \
		done ; \
    done

uninstall:
	rm -rf ${DESTDIR}${PREFIX}${PLUGINSDIR}*

clean:
	find . -name "*.py[co]" -exec rm -f {} \;
