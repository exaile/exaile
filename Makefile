PREFIX ?= $(DESTDIR)/usr/local
LIBINSTALLDIR ?= /lib
XDGCONFDIR ?= $(DESTDIR)/etc/xdg

EXAILELIBDIR = $(DESTDIR)$(PREFIX)$(LIBINSTALLDIR)/exaile
EXAILESHAREDIR = $(DESTDIR)$(PREFIX)/share/exaile


all: compile
	@echo "Ready to install..."

compile:
	python -m compileall -q xl xlgui
	-python -O -m compileall -q xl xlgui
	cd plugins && make && cd ..

make-install-dirs:
	mkdir -p $(DESTDIR)$(PREFIX)/bin
	mkdir -p $(EXAILELIBDIR)
	mkdir -p $(EXAILELIBDIR)/xl
	mkdir -p $(EXAILELIBDIR)/xl/metadata
	mkdir -p $(EXAILELIBDIR)/xl/player
	mkdir -p $(EXAILELIBDIR)/xlgui
	mkdir -p $(EXAILELIBDIR)/xlgui/panel
	mkdir -p $(EXAILELIBDIR)/xlgui/prefs
	mkdir -p $(EXAILESHAREDIR)
	mkdir -p $(EXAILESHAREDIR)/data
	mkdir -p $(EXAILESHAREDIR)/data/images
	mkdir -p $(EXAILESHAREDIR)/data/glade
	mkdir -p $(DESTDIR)$(PREFIX)/share/pixmaps
	mkdir -p $(DESTDIR)$(PREFIX)/share/applications
	mkdir -p $(XDGCONFDIR)/exaile

uninstall:
	rm -f  $(DESTDIR)$(PREFIX)/bin/exaile
	rm -rf $(EXAILELIBDIR)
	rm -rf $(EXAILELIBDIR)/xl
	rm -rf $(EXAILELIBDIR)/xl/metadata
	rm -rf $(EXAILELIBDIR)/xl/player
	rm -rf $(EXAILELIBDIR)/xlgui
	rm -rf $(EXAILELIBDIR)/xlgui/panel
	rm -rf $(EXAILELIBDIR)/xlgui/prefs
	rm -rf $(EXAILESHAREDIR)
	rm -rf $(EXAILESHAREDIR)/data
	rm -rf $(EXAILESHAREDIR)/data/images
	rm -rf $(EXAILESHAREDIR)/data/glade
	rm -rf $(XDGCONFDIR)/exaile
	rm -f $(DESTDIR)$(PREFIX)/share/applications/exaile.desktop
	rm -f $(DESTDIR)$(PREFIX)/share/pixmaps/exaile.png
	cd plugins && make uninstall && cd ..

install: make-install-dirs install-target locale

install_no_locale: make-install-dirs install-target

install-target:
	install -m 644 exaile.py $(EXAILELIBDIR)	
	-install -m 644 xl/*.py[co] $(EXAILELIBDIR)/xl
	install -m 644 xl/*.py $(EXAILELIBDIR)/xl
	-install -m 644 xl/metadata/*.py[co] $(EXAILELIBDIR)/xl/metadata
	install -m 644 xl/metadata/*.py $(EXAILELIBDIR)/xl/metadata
	-install -m 644 xl/player/*.py[co] $(EXAILELIBDIR)/xl/player
	install -m 644 xl/player/*.py $(EXAILELIBDIR)/xl/player
	-install -m 644 xlgui/*.py[co] $(EXAILELIBDIR)/xlgui
	install -m 644 xlgui/*.py $(EXAILELIBDIR)/xlgui
	-install -m 644 xlgui/panel/*.py[co] $(EXAILELIBDIR)/xlgui/panel
	install -m 644 xlgui/panel/*.py $(EXAILELIBDIR)/xlgui/panel
	-install -m 644 xlgui/prefs/*.py[co] $(EXAILELIBDIR)/xlgui/prefs
	install -m 644 xlgui/prefs/*.py $(EXAILELIBDIR)/xlgui/prefs
	install -m 644 data/images/*.png $(EXAILESHAREDIR)/data/images
	install -m 644 data/glade/*.glade $(EXAILESHAREDIR)/data/glade
	install -m 644 data/images/icon.png \
		$(DESTDIR)$(PREFIX)/share/pixmaps/exaile.png
	install -m 644 data/exaile.desktop \
		$(DESTDIR)$(PREFIX)/share/applications/	
	install -m 644 data/config/settings.ini $(XDGCONFDIR)/exaile
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

locale:
	for f in `find po -name exaile.mo` ; do \
	  install -d -m 755 \
	    `echo $$f | sed "s|^po|$(DESTDIR)$(PREFIX)/share/locale|" | \
	      xargs dirname` && \
	  install -m 644 $$f \
	    `echo $$f | sed "s|^po|$(DESTDIR)$(PREFIX)/share/locale|"` ; \
	  done

plugins_extra_install:
	cd plugins && make extra_install DESTDIR=$(DESTDIR) PREFIX=$(PREFIX) \
	    && cd ..

plugins_dist:
	cd plugins && make dist && cd ..

clean:
	-find . -name "*.py[co]" -exec rm -f {} \;
	find . -name "*.class" -exec rm -f {} \;
	find . -name "*.bak" -exec rm -f {} \;
	cd plugins && make clean && cd ..

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


