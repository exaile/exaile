PREFIX ?= /usr/local
LIBDIR ?= /lib

all: compile
	@echo "Ready to install..."

compile:
	python -O -m compileall xl lib xlgui

make-install-dirs:
	mkdir -p $(DESTDIR)$(PREFIX)/bin
	mkdir -p $(DESTDIR)$(PREFIX)$(LIBDIR)/exaile
	mkdir -p $(DESTDIR)$(PREFIX)$(LIBDIR)/exaile/lib
	mkdir -p $(DESTDIR)$(PREFIX)$(LIBDIR)/exaile/xl
	mkdir -p $(DESTDIR)$(PREFIX)$(LIBDIR)/exaile/xl/metadata
	mkdir -p $(DESTDIR)$(PREFIX)$(LIBDIR)/exaile/xlgui
	mkdir -p $(DESTDIR)$(PREFIX)$(LIBDIR)/exaile/xlgui/panel
	mkdir -p $(DESTDIR)$(PREFIX)$(LIBDIR)/exaile/xlgui/prefs
	mkdir -p $(DESTDIR)$(PREFIX)/share/exaile
	mkdir -p $(DESTDIR)$(PREFIX)/share/exaile/data
	mkdir -p $(DESTDIR)$(PREFIX)/share/exaile/data/images
	mkdir -p $(DESTDIR)$(PREFIX)/share/exaile/data/glade

uninstall:
	rm -f  $(DESTDIR)$(PREFIX)/bin/exaile
	rm -rf $(DESTDIR)$(PREFIX)$(LIBDIR)/exaile
	rm -rf $(DESTDIR)$(PREFIX)$(LIBDIR)/exaile/lib
	rm -rf $(DESTDIR)$(PREFIX)$(LIBDIR)/exaile/xl
	rm -rf $(DESTDIR)$(PREFIX)$(LIBDIR)/exaile/xl/metadata
	rm -rf $(DESTDIR)$(PREFIX)$(LIBDIR)/exaile/xlgui
	rm -rf $(DESTDIR)$(PREFIX)$(LIBDIR)/exaile/xlgui/panel
	rm -rf $(DESTDIR)$(PREFIX)$(LIBDIR)/exaile/xlgui/prefs
	rm -rf $(DESTDIR)$(PREFIX)/share/exaile
	rm -rf $(DESTDIR)$(PREFIX)/share/exaile/data
	rm -rf $(DESTDIR)$(PREFIX)/share/exaile/data/images
	rm -rf $(DESTDIR)$(PREFIX)/share/exaile/data/glade
	cd plugins && make uninstall && cd ..


install: make-install-dirs compile
	install -m 644 exaile.py $(DESTDIR)$(PREFIX)$(LIBDIR)/exaile	
	install -m 644 xl/*.py[co] $(DESTDIR)$(PREFIX)$(LIBDIR)/exaile/xl
	install -m 644 xl/*.py $(DESTDIR)$(PREFIX)$(LIBDIR)/exaile/xl
	install -m 644 xl/metadata/*.py[co] \
		$(DESTDIR)$(PREFIX)$(LIBDIR)/exaile/xl/metadata
	install -m 644 xl/metadata/*.py \
		$(DESTDIR)$(PREFIX)$(LIBDIR)/exaile/xl/metadata
	install -m 644 xlgui/*.py[co] $(DESTDIR)$(PREFIX)$(LIBDIR)/exaile/xlgui
	install -m 644 xlgui/*.py $(DESTDIR)$(PREFIX)$(LIBDIR)/exaile/xlgui
	install -m 644 xlgui/panel/*.py[co] \
		$(DESTDIR)$(PREFIX)$(LIBDIR)/exaile/xlgui/panel
	install -m 644 xlgui/panel/*.py \
		$(DESTDIR)$(PREFIX)$(LIBDIR)/exaile/xlgui/panel
	install -m 644 xlgui/prefs/*.py[co] \
		$(DESTDIR)$(PREFIX)$(LIBDIR)/exaile/xlgui/prefs
	install -m 644 xlgui/prefs/*.py \
		$(DESTDIR)$(PREFIX)$(LIBDIR)/exaile/xlgui/prefs
	install -m 644 lib/*.py[co] $(DESTDIR)$(PREFIX)$(LIBDIR)/exaile/lib
	install -m 644 lib/*.py $(DESTDIR)$(PREFIX)$(LIBDIR)/exaile/lib
	install -m 644 data/images/*.png \
		$(DESTDIR)$(PREFIX)/share/exaile/data/images
	install -m 644 data/glade/*.glade \
		$(DESTDIR)$(PREFIX)/share/exaile/data/glade
	cd $(DESTDIR)$(PREFIX)/bin && \
	 /bin/echo -e \
	 "#!/bin/sh\n" \
	 "cd $(PREFIX)/share/exaile\n" \
	 "exec python $(PREFIX)$(LIBDIR)/exaile/exaile.py " \
	 "--datadir=$(PREFIX)/share/exaile/data --startgui \"\$$@\"" \
	 > exaile && \
	chmod 755 exaile

	cd plugins && make install PREFIX=$(PREFIX)

plugins_dist:
	cd plugins && make dist && cd ..

clean:
	find . -name "*.py[co]" -exec rm -f {} \;
	find . -name "*.class" -exec rm -f {} \;
	find . -name "*.bak" -exec rm -f {} \;
	rm -rf doc
	cd plugins && make clean && cd ..

doc: docclean
	mkdir -p ./doc/
	epydoc -n Exaile -vo ./doc/ --html xl xlgui || echo "Epydoc not available, skipping docs generation"
	make clean

docclean:
	rm -rf ./doc/*

test:
	python runtests.py all

testplugins:
	python runtests.py plugins

testmain:
	python runtests.py main

doctests:
	python runtests.py doctests


commit: test clean
	./commit || (bzr pull && bzr commit)
	@echo "Use bzr push to send to launchpad"
