PREFIX ?= /usr/local
LIBINSTALLDIR ?= /lib

all: compile
	@echo "Ready to install..."

compile:
	python -m compileall -q xl lib xlgui
	-python -O -m compileall -q xl lib xlgui
	cd plugins && make && cd ..

make-install-dirs:
	mkdir -p $(DESTDIR)$(PREFIX)/bin
	mkdir -p $(DESTDIR)$(PREFIX)$(LIBINSTALLDIR)/exaile
	mkdir -p $(DESTDIR)$(PREFIX)$(LIBINSTALLDIR)/exaile/lib
	mkdir -p $(DESTDIR)$(PREFIX)$(LIBINSTALLDIR)/exaile/xl
	mkdir -p $(DESTDIR)$(PREFIX)$(LIBINSTALLDIR)/exaile/xl/metadata
	mkdir -p $(DESTDIR)$(PREFIX)$(LIBINSTALLDIR)/exaile/xlgui
	mkdir -p $(DESTDIR)$(PREFIX)$(LIBINSTALLDIR)/exaile/xlgui/panel
	mkdir -p $(DESTDIR)$(PREFIX)$(LIBINSTALLDIR)/exaile/xlgui/prefs
	mkdir -p $(DESTDIR)$(PREFIX)/share/exaile
	mkdir -p $(DESTDIR)$(PREFIX)/share/exaile/data
	mkdir -p $(DESTDIR)$(PREFIX)/share/exaile/data/images
	mkdir -p $(DESTDIR)$(PREFIX)/share/exaile/data/glade
	mkdir -p $(DESTDIR)$(PREFIX)/share/pixmaps
	mkdir -p $(DESTDIR)$(PREFIX)/share/applications

uninstall:
	rm -f  $(DESTDIR)$(PREFIX)/bin/exaile
	rm -rf $(DESTDIR)$(PREFIX)$(LIBINSTALLDIR)/exaile
	rm -rf $(DESTDIR)$(PREFIX)$(LIBINSTALLDIR)/exaile/lib
	rm -rf $(DESTDIR)$(PREFIX)$(LIBINSTALLDIR)/exaile/xl
	rm -rf $(DESTDIR)$(PREFIX)$(LIBINSTALLDIR)/exaile/xl/metadata
	rm -rf $(DESTDIR)$(PREFIX)$(LIBINSTALLDIR)/exaile/xlgui
	rm -rf $(DESTDIR)$(PREFIX)$(LIBINSTALLDIR)/exaile/xlgui/panel
	rm -rf $(DESTDIR)$(PREFIX)$(LIBINSTALLDIR)/exaile/xlgui/prefs
	rm -rf $(DESTDIR)$(PREFIX)/share/exaile
	rm -rf $(DESTDIR)$(PREFIX)/share/exaile/data
	rm -rf $(DESTDIR)$(PREFIX)/share/exaile/data/images
	rm -rf $(DESTDIR)$(PREFIX)/share/exaile/data/glade
	rm -f $(DESTDIR)$(PREFIX)/share/applications/exaile.desktop
	rm -f $(DESTDIR)$(PREFIX)/share/pixmaps/exaile.png
	cd plugins && make uninstall && cd ..


install: make-install-dirs
	install -m 644 exaile.py $(DESTDIR)$(PREFIX)$(LIBINSTALLDIR)/exaile	
	-install -m 644 xl/*.py[co] $(DESTDIR)$(PREFIX)$(LIBINSTALLDIR)/exaile/xl
	install -m 644 xl/*.py $(DESTDIR)$(PREFIX)$(LIBINSTALLDIR)/exaile/xl
	-install -m 644 xl/metadata/*.py[co] \
		$(DESTDIR)$(PREFIX)$(LIBINSTALLDIR)/exaile/xl/metadata
	install -m 644 xl/metadata/*.py \
		$(DESTDIR)$(PREFIX)$(LIBINSTALLDIR)/exaile/xl/metadata
	-install -m 644 xlgui/*.py[co] $(DESTDIR)$(PREFIX)$(LIBINSTALLDIR)/exaile/xlgui
	install -m 644 xlgui/*.py $(DESTDIR)$(PREFIX)$(LIBINSTALLDIR)/exaile/xlgui
	-install -m 644 xlgui/panel/*.py[co] \
		$(DESTDIR)$(PREFIX)$(LIBINSTALLDIR)/exaile/xlgui/panel
	install -m 644 xlgui/panel/*.py \
		$(DESTDIR)$(PREFIX)$(LIBINSTALLDIR)/exaile/xlgui/panel
	-install -m 644 xlgui/prefs/*.py[co] \
		$(DESTDIR)$(PREFIX)$(LIBINSTALLDIR)/exaile/xlgui/prefs
	install -m 644 xlgui/prefs/*.py \
		$(DESTDIR)$(PREFIX)$(LIBINSTALLDIR)/exaile/xlgui/prefs
	for f in `find po -name exaile.mo` ; do \
	  install -d -m 755 \
	    `echo $$f | sed "s|^po|$(DESTDIR)$(PREFIX)/share/locale|" | \
	      xargs dirname` && \
	  install -m 644 $$f \
	    `echo $$f | sed "s|^po|$(DESTDIR)$(PREFIX)/share/locale|"` ; \
	  done
	install -m 644 data/images/*.png \
		$(DESTDIR)$(PREFIX)/share/exaile/data/images
	install -m 644 data/glade/*.glade \
		$(DESTDIR)$(PREFIX)/share/exaile/data/glade
	install -m 644 data/images/largeicon.png \
		$(DESTDIR)$(PREFIX)/share/pixmaps/exaile.png
	install -m 644 data/exaile.desktop \
		$(DESTDIR)$(PREFIX)/share/applications/	
	# the printf here is for bsd compat, dont use echo!
	cd $(DESTDIR)$(PREFIX)/bin && \
	 printf "#!/bin/sh\n\
	 cd $(PREFIX)/share/exaile\n\
	 exec python $(PREFIX)$(LIBINSTALLDIR)/exaile/exaile.py \
	 --datadir=$(PREFIX)/share/exaile/data --startgui \"\$$@\"" \
	 > exaile && \
	chmod 755 exaile
	cd plugins && make install DESTDIR=$(DESTDIR) PREFIX=$(PREFIX) \
		&& cd ..

plugins_extra_install:
	cd plugins && make extra_install DESTDIR=$(DESTDIR) PREFIX=$(PREFIX) \
	    && cd ..

plugins_dist:
	cd plugins && make dist && cd ..

clean:
	-find . -name "*.py[co]" -exec rm -f {} \;
	find . -name "*.class" -exec rm -f {} \;
	find . -name "*.bak" -exec rm -f {} \;
	rm -f po/POTFILES.in
	rm -f po/messages.pot
	cd plugins && make clean && cd ..
	rm -f data/plugins

pot:
	@echo "[encoding: UTF-8]" > po/POTFILES.in
	find xl -name "*.py" >> po/POTFILES.in
	find xlgui -name "*.py" >> po/POTFILES.in
	find data/glade/ -name "*.glade" >> po/POTFILES.in
	find plugins -name "*.py" >> po/POTFILES.in
	find plugins -name "*.glade" >> po/POTFILES.in
	python tools/createpot.py

translations:
	python tools/createpot.py compile

potball:
	tar --bzip2 --format=posix -cf exaile-po.tar.bz2 po/ \
	    --transform s/po/./

.PHONY: dist 

# TODO: embed version information
dist:
	mkdir -p dist
	rm -rf dist/copy
	bzr co --lightweight ./ dist/copy
	tar --bzip2 --format=posix -cf dist/exaile-dist.tar.bz2 dist/copy \
	    --exclude=dist/copy/.bzr* --transform s/dist\\/copy/exaile/


