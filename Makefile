PYTHON2_CMD	?= /usr/bin/python2

PREFIX 		?= /usr/local
LIBINSTALLDIR 	?= /lib
XDGCONFDIR 	?= /etc/xdg

EXAILEBINDIR  = $(DESTDIR)$(PREFIX)/bin
EXAILELIBDIR 	= $(DESTDIR)$(PREFIX)$(LIBINSTALLDIR)/exaile
EXAILESHAREDIR 	= $(DESTDIR)$(PREFIX)/share/exaile
EXAILECONFDIR 	= $(DESTDIR)$(XDGCONFDIR)/exaile

.PHONY: dist test coverage clean sanitycheck

all: compile locale manpage
	@echo "Ready to install..."

# The no_locale stuff is by request of BSD people, please ensure
# all methods that deal with locale stuff have a no_locale variant
all_no_locale: compile
	@echo "Ready to install..."

compile:
	$(PYTHON2_CMD) -m compileall -q xl xlgui
	-$(PYTHON2_CMD) -O -m compileall -q xl xlgui
	$(MAKE) -C plugins compile

make-install-dirs:
	mkdir -p $(EXAILEBINDIR)
	mkdir -p $(EXAILELIBDIR)
	mkdir -p $(EXAILELIBDIR)/xl
	mkdir -p $(EXAILELIBDIR)/xl/metadata
	mkdir -p $(EXAILELIBDIR)/xl/player
	mkdir -p $(EXAILELIBDIR)/xl/migrations
	mkdir -p $(EXAILELIBDIR)/xl/migrations/database
	mkdir -p $(EXAILELIBDIR)/xl/migrations/settings
	mkdir -p $(EXAILELIBDIR)/xl/trax
	mkdir -p $(EXAILELIBDIR)/xlgui
	mkdir -p $(EXAILELIBDIR)/xlgui/panel
	mkdir -p $(EXAILELIBDIR)/xlgui/preferences
	mkdir -p $(EXAILELIBDIR)/xlgui/widgets
	mkdir -p $(EXAILESHAREDIR)
	mkdir -p $(EXAILESHAREDIR)/data
	mkdir -p $(EXAILESHAREDIR)/data/images/16x16
	mkdir -p $(EXAILESHAREDIR)/data/images/22x22
	mkdir -p $(EXAILESHAREDIR)/data/images/24x24
	mkdir -p $(EXAILESHAREDIR)/data/images/32x32
	mkdir -p $(EXAILESHAREDIR)/data/images/48x48
	mkdir -p $(EXAILESHAREDIR)/data/images/scalable
	mkdir -p $(EXAILESHAREDIR)/data/ui
	mkdir -p $(EXAILESHAREDIR)/data/ui/preferences
	mkdir -p $(EXAILESHAREDIR)/data/ui/widgets
	mkdir -p $(EXAILESHAREDIR)/data/migrations
	mkdir -p $(EXAILESHAREDIR)/data/migrations/migration_200907100931
	mkdir -p $(DESTDIR)$(PREFIX)/share/pixmaps
	mkdir -p $(DESTDIR)$(PREFIX)/share/applications
	mkdir -p $(DESTDIR)$(PREFIX)/share/man/man1
	mkdir -p $(DESTDIR)$(PREFIX)/share/dbus-1/services
	mkdir -p $(EXAILECONFDIR)

uninstall:
	rm -f  $(EXAILEBINDIR)/exaile
	rm -rf $(EXAILELIBDIR)
	rm -rf $(EXAILESHAREDIR)
	rm -rf $(EXAILECONFDIR)/exaile
	rm -f $(DESTDIR)$(PREFIX)/share/applications/exaile.desktop
	rm -f $(DESTDIR)$(PREFIX)/share/pixmaps/exaile.png
	rm -f $(DESTDIR)$(PREFIX)/share/man/man1/exaile.1.gz
	rm -f $(DESTDIR)$(PREFIX)/share/dbus-1/services/org.exaile.Exaile.service
	$(MAKE) -C plugins uninstall

install: install-target install-locale

install_no_locale: install-target

install-target: make-install-dirs
	install -m 644 exaile.py $(EXAILELIBDIR)	
	-install -m 644 xl/*.py[co] $(EXAILELIBDIR)/xl
	install -m 644 xl/*.py $(EXAILELIBDIR)/xl
	-install -m 644 xl/metadata/*.py[co] $(EXAILELIBDIR)/xl/metadata
	install -m 644 xl/metadata/*.py $(EXAILELIBDIR)/xl/metadata
	-install -m 644 xl/player/*.py[co] $(EXAILELIBDIR)/xl/player
	install -m 644 xl/player/*.py $(EXAILELIBDIR)/xl/player
	-install -m 644 xl/migrations/*.py[co] $(EXAILELIBDIR)/xl/migrations
	install -m 644 xl/migrations/*.py $(EXAILELIBDIR)/xl/migrations
	-install -m 644 xl/migrations/database/*.py[co] $(EXAILELIBDIR)/xl/migrations/database/
	install -m 644 xl/migrations/database/*.py $(EXAILELIBDIR)/xl/migrations/database/
	-install -m 644 xl/migrations/settings/*.py[co] $(EXAILELIBDIR)/xl/migrations/settings/
	install -m 644 xl/migrations/settings/*.py $(EXAILELIBDIR)/xl/migrations/settings/
	-install -m 644 xl/trax/*.py[co] $(EXAILELIBDIR)/xl/trax
	install -m 644 xl/trax/*.py $(EXAILELIBDIR)/xl/trax
	-install -m 644 xlgui/*.py[co] $(EXAILELIBDIR)/xlgui
	install -m 644 xlgui/*.py $(EXAILELIBDIR)/xlgui
	-install -m 644 xlgui/panel/*.py[co] $(EXAILELIBDIR)/xlgui/panel
	install -m 644 xlgui/panel/*.py $(EXAILELIBDIR)/xlgui/panel
	-install -m 644 xlgui/preferences/*.py[co] $(EXAILELIBDIR)/xlgui/preferences
	install -m 644 xlgui/preferences/*.py $(EXAILELIBDIR)/xlgui/preferences
	-install -m 644 xlgui/widgets/*.py[co] $(EXAILELIBDIR)/xlgui/widgets
	install -m 644 xlgui/widgets/*.py $(EXAILELIBDIR)/xlgui/widgets
	install -m 644 data/images/16x16/*.png $(EXAILESHAREDIR)/data/images/16x16
	install -m 644 data/images/22x22/*.png $(EXAILESHAREDIR)/data/images/22x22
	install -m 644 data/images/24x24/*.png $(EXAILESHAREDIR)/data/images/24x24
	install -m 644 data/images/32x32/*.png $(EXAILESHAREDIR)/data/images/32x32
	install -m 644 data/images/48x48/*.png $(EXAILESHAREDIR)/data/images/48x48
	install -m 644 data/images/scalable/*.svg $(EXAILESHAREDIR)/data/images/scalable
	install -m 644 data/images/*.png $(EXAILESHAREDIR)/data/images
	install -m 644 data/images/48x48/exaile.png \
		$(DESTDIR)$(PREFIX)/share/pixmaps/exaile.png
	install -m 644 data/ui/*.ui $(EXAILESHAREDIR)/data/ui
	install -m 644 data/ui/preferences/*.ui $(EXAILESHAREDIR)/data/ui/preferences
	install -m 644 data/ui/widgets/*.ui $(EXAILESHAREDIR)/data/ui/widgets
	install -m 644 data/migrations/*.py $(EXAILESHAREDIR)/data/migrations/
	install -m 644 data/migrations/migration_200907100931/*.py \
	    	$(EXAILESHAREDIR)/data/migrations/migration_200907100931/
	install -m 644 data/exaile.desktop \
		$(DESTDIR)$(PREFIX)/share/applications/	
	-install -m 644 exaile.1.gz $(DESTDIR)$(PREFIX)/share/man/man1/
	install -m 644 data/config/settings.ini $(EXAILECONFDIR)
	tools/generate-launcher "$(DESTDIR)" "$(PREFIX)" "$(LIBINSTALLDIR)" && \
	  chmod 755 $(DESTDIR)$(PREFIX)/bin/exaile
	sed "s|\@bindir\@|$(EXAILEBINDIR)|" data/org.exaile.Exaile.service.in > \
		$(DESTDIR)$(PREFIX)/share/dbus-1/services/org.exaile.Exaile.service
	$(MAKE) -C plugins install

locale:
	$(MAKE) -C po locale

install-locale:
	for f in `find po -name exaile.mo` ; do \
	  install -d -m 755 \
	    `echo $$f | sed "s|^po|$(DESTDIR)$(PREFIX)/share/locale|" | \
	      xargs dirname` && \
	  install -m 644 $$f \
	    `echo $$f | sed "s|^po|$(DESTDIR)$(PREFIX)/share/locale|"` ; \
	  done

plugins_dist:
	$(MAKE) -C plugins dist

# The sed call in -h removes the indent from group headers to work around
# help2man's incompatibility with optparse's grouping.
# The sed call in -v removes the ASCII art from Exaile's --version and
# prints out the proper "$program $version" text.
manpage:
	help2man -n "music manager and player" -N \
	  -h './exaile --help | sed "s/^  //"' \
	  -v './exaile --version | sed -n "4 s/.* v\\(.*\\)/exaile \\1/ p"' \
	  ./exaile \
	  | gzip -9 > exaile.1.gz

clean:
	-find . -name "*.~[0-9]~" -exec rm -f {} \;
	-find . -name "*.py[co]" -exec rm -f {} \;
	find po/* -depth -type d -exec rm -r {} \;
	rm -f exaile.1.gz
	$(MAKE) -C plugins clean

# The "[type: gettext/glade]" helps intltool recognize .ui files as glade format
pot:
	echo "[encoding: UTF-8]" > po/POTFILES.in && \
	  find xl -name "*.py" >> po/POTFILES.in && \
	  find xlgui -name "*.py" >> po/POTFILES.in && \
	  find data/ui/ -name "*.ui" | sed 's/^/[type: gettext\/glade]/' >> po/POTFILES.in && \
	  find plugins -name "*.py" | grep -v treeviewtest >> po/POTFILES.in && \
	  find plugins -name "*.ui" | grep -v treeviewtest | sed 's/^/[type: gettext\/glade]/' >> po/POTFILES.in && \
	  find plugins -name PLUGININFO | grep -v treeviewtest >> po/POTFILES.in && \
	  cd po && XGETTEXT_ARGS="--language=Python --add-comments=TRANSLATORS" \
	    intltool-update --pot --gettext-package=messages --verbose && cd ..

potball:
	tar --bzip2 --format=posix -cf build/exaile-po.tar.bz2 po/ \
	    --transform s/po/./


dist:
	mkdir -p dist
	rm -rf dist/copy
	bzr export dist/copy/
	./tools/dist.sh
	rm -rf dist/copy

test:
	nosetests -w tests

test_coverage:
	rm -rf coverage/
	rm -f .coverage
	nosetests -w tests --with-coverage --cover-package=xl; \
	mkdir -p coverage; \
	coverage html -d coverage

lint_errors:
	-pylint -e --rcfile tools/pylint.cfg xl xlgui 2> /dev/null

sanitycheck: lint_errors test
