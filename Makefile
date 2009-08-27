PREFIX ?= /usr/local
LIBINSTALLDIR ?= /lib
XDGCONFDIR ?= /etc/xdg

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
	mkdir -p $(EXAILESHAREDIR)/data/images/16x16
	mkdir -p $(EXAILESHAREDIR)/data/images/22x22
	mkdir -p $(EXAILESHAREDIR)/data/images/24x24
	mkdir -p $(EXAILESHAREDIR)/data/images/32x32
	mkdir -p $(EXAILESHAREDIR)/data/images/48x48
	mkdir -p $(EXAILESHAREDIR)/data/images/svg
	mkdir -p $(EXAILESHAREDIR)/data/glade
	mkdir -p $(EXAILESHAREDIR)/data/migrations
	mkdir -p $(EXAILESHAREDIR)/data/migrations/migration_200907100931
	mkdir -p $(DESTDIR)$(PREFIX)/share/pixmaps
	mkdir -p $(DESTDIR)$(PREFIX)/share/applications
	mkdir -p $(DESTDIR)$(XDGCONFDIR)/exaile

uninstall:
	rm -f  $(DESTDIR)$(PREFIX)/bin/exaile
	rm -rf $(EXAILELIBDIR)
	rm -rf $(EXAILESHAREDIR)
	rm -rf $(DESTDIR)$(XDGCONFDIR)/exaile
	rm -f $(DESTDIR)$(PREFIX)/share/applications/exaile.desktop
	rm -f $(DESTDIR)$(PREFIX)/share/pixmaps/exaile.png
	cd plugins && make uninstall && cd ..

install: install-target locale install-locale

install_no_locale: install-target

install-target: make-install-dirs
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
	install -m 644 data/images/16x16/*.png $(EXAILESHAREDIR)/data/images/16x16
	install -m 644 data/images/22x22/*.png $(EXAILESHAREDIR)/data/images/22x22
	install -m 644 data/images/24x24/*.png $(EXAILESHAREDIR)/data/images/24x24
	install -m 644 data/images/32x32/*.png $(EXAILESHAREDIR)/data/images/32x32
	install -m 644 data/images/48x48/*.png $(EXAILESHAREDIR)/data/images/48x48
	install -m 644 data/images/svg/*.svg $(EXAILESHAREDIR)/data/images/svg
	install -m 644 data/images/*.png $(EXAILESHAREDIR)/data/images
	install -m 644 data/images/48x48/exaile.png \
		$(DESTDIR)$(PREFIX)/share/pixmaps/exaile.png
	install -m 644 data/glade/*.glade $(EXAILESHAREDIR)/data/glade
	install -m 644 data/migrations/*.py $(EXAILESHAREDIR)/migrations/
	install -m 644 data/migrations/migration_200907100931/*.py \
	    	$(EXAILESHAREDIR)/migrations/migration_200907100931/
	install -m 644 data/exaile.desktop \
		$(DESTDIR)$(PREFIX)/share/applications/	
	install -m 644 data/config/settings.ini $(DESTDIR)$(XDGCONFDIR)/exaile
	# the printf here is for bsd compat, dont use echo!
	cd $(DESTDIR)$(PREFIX)/bin && \
	 printf "#!/bin/sh\n\
	 exec python $(PREFIX)$(LIBINSTALLDIR)/exaile/exaile.py \
	 --datadir=$(PREFIX)/share/exaile/data --startgui \"\$$@\"" \
	 > exaile && \
	 chmod 755 exaile
	cd plugins && make install DESTDIR=$(DESTDIR) PREFIX=$(PREFIX) \
		&& cd ..

locale:
	cd po && find . -name "*.po" -exec ../tools/compilepo.sh {} \; && cd ..

install-locale:
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
	find po/* -depth -type d -exec rm -r {} \;
	cd plugins && make clean && cd ..

pot:
	@echo "[encoding: UTF-8]" > po/POTFILES.in
	find xl -name "*.py" >> po/POTFILES.in
	find xlgui -name "*.py" >> po/POTFILES.in
	find data/glade/ -name "*.glade" >> po/POTFILES.in
	find plugins -name "*.py" >> po/POTFILES.in
	find plugins -name "*.glade" >> po/POTFILES.in
	find plugins -name PLUGININFO >> po/POTFILES.in
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


