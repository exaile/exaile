PYTHON3_CMD   ?= python3
PYTEST        ?= py.test-3
BLACK         ?= black

PREFIX         = /usr/local
EPREFIX        = $(PREFIX)

LIBINSTALLDIR  = $(EPREFIX)/lib
DATADIR        = $(PREFIX)/share
MANPREFIX      = $(PREFIX)/share
# /etc if PREFIX is /usr, $PREFIX/etc otherwise.
ETCDIR        := $(shell [ "$(PREFIX)" = "/usr" ] && echo /etc || echo "$(PREFIX)/etc")
XDGCONFDIR     = $(ETCDIR)/xdg

# Find bash-completion's completions directory, first by checking pkg-config,
# then using a hard-coded path. Override BASHCOMPDIR if it's still wrong for
# your OS.
BASHCOMPDIR   := $(shell pkg-config --define-variable=prefix="$(PREFIX)" \
  --variable=completionsdir bash-completion 2> /dev/null \
  || echo "$(PREFIX)/share/bash-completion/completions")

# Like above but for Fish.
FISHCOMPDIR   := $(shell pkg-config \
  --variable=completionsdir fish 2> /dev/null \
  || echo "$(PREFIX)/share/fish/vendor_completions.d")

EXAILEBINDIR   = $(DESTDIR)$(EPREFIX)/bin
EXAILELIBDIR   = $(DESTDIR)$(LIBINSTALLDIR)/exaile
EXAILESHAREDIR = $(DESTDIR)$(DATADIR)/exaile
EXAILECONFDIR  = $(DESTDIR)$(XDGCONFDIR)/exaile
EXAILEMANDIR   = $(DESTDIR)$(MANPREFIX)/man

.PHONY: all all_no_locale builddir compile make-install-dirs uninstall \
	install install_no_locale install-target locale install-locale \
	plugins-dist manpage completion clean pot potball dist check-doc test \
	test_coverage lint_errors sanitycheck format

all: compile completion locale manpage
	@echo "Ready to install..."

# The no_locale stuff is by request of BSD people, please ensure
# all methods that deal with locale stuff have a no_locale variant
all_no_locale: compile completion manpage
	@echo "Ready to install..."

builddir:
	mkdir -p build

compile:
	$(PYTHON3_CMD) -m compileall -q xl xlgui
	$(PYTHON3_CMD) -O -m compileall -q xl xlgui
	$(MAKE) -C plugins compile

make-install-dirs:
	install -d -m 755 $(EXAILEBINDIR)
	install -d -m 755 $(EXAILELIBDIR)
	install -d -m 755 $(EXAILELIBDIR)/xl
	install -d -m 755 $(EXAILELIBDIR)/xl/externals
	install -d -m 755 $(EXAILELIBDIR)/xl/metadata
	install -d -m 755 $(EXAILELIBDIR)/xl/player
	install -d -m 755 $(EXAILELIBDIR)/xl/player/gst
	install -d -m 755 $(EXAILELIBDIR)/xl/migrations
	install -d -m 755 $(EXAILELIBDIR)/xl/migrations/database
	install -d -m 755 $(EXAILELIBDIR)/xl/migrations/settings
	install -d -m 755 $(EXAILELIBDIR)/xl/trax
	install -d -m 755 $(EXAILELIBDIR)/xlgui
	install -d -m 755 $(EXAILELIBDIR)/xlgui/panel
	install -d -m 755 $(EXAILELIBDIR)/xlgui/preferences
	install -d -m 755 $(EXAILELIBDIR)/xlgui/widgets
	install -d -m 755 $(EXAILESHAREDIR)
	install -d -m 755 $(EXAILESHAREDIR)/data
	install -d -m 755 $(EXAILESHAREDIR)/data/images/16x16
	install -d -m 755 $(EXAILESHAREDIR)/data/images/22x22
	install -d -m 755 $(EXAILESHAREDIR)/data/images/24x24
	install -d -m 755 $(EXAILESHAREDIR)/data/images/32x32
	install -d -m 755 $(EXAILESHAREDIR)/data/images/48x48
	install -d -m 755 $(EXAILESHAREDIR)/data/images/scalable
	install -d -m 755 $(EXAILESHAREDIR)/data/ui
	install -d -m 755 $(EXAILESHAREDIR)/data/ui/panel
	install -d -m 755 $(EXAILESHAREDIR)/data/ui/preferences
	install -d -m 755 $(EXAILESHAREDIR)/data/ui/preferences/widgets
	install -d -m 755 $(EXAILESHAREDIR)/data/ui/widgets
	install -d -m 755 $(DESTDIR)$(DATADIR)/pixmaps
	install -d -m 755 $(DESTDIR)$(DATADIR)/appdata
	install -d -m 755 $(DESTDIR)$(DATADIR)/applications
	install -d -m 755 $(DESTDIR)$(DATADIR)/dbus-1/services
	install -d -m 755 $(EXAILEMANDIR)/man1
	install -d -m 755 $(DESTDIR)$(BASHCOMPDIR)
	install -d -m 755 $(DESTDIR)$(FISHCOMPDIR)
	install -d -m 755 $(EXAILECONFDIR)

uninstall:
	rm -f  $(EXAILEBINDIR)/exaile
	rm -rf $(EXAILELIBDIR)
	rm -rf $(EXAILESHAREDIR)
	rm -rf $(EXAILECONFDIR)
	rm -f $(DESTDIR)$(DATADIR)/applications/exaile.desktop
	rm -f $(DESTDIR)$(DATADIR)/pixmaps/exaile.png
	rm -f $(DESTDIR)$(DATADIR)/appdata/exaile.appdata.xml
	rm -f $(DESTDIR)$(DATADIR)/dbus-1/services/org.exaile.Exaile.service
	rm -f $(EXAILEMANDIR)/man1/exaile.1.gz
	rm -f $(DESTDIR)$(BASHCOMPDIR)/exaile
	rm -f $(DESTDIR)$(FISHCOMPDIR)/exaile.fish
	$(MAKE) -C plugins uninstall
	find $(DESTDIR)$(DATADIR)/locale -name "exaile.mo" -exec rm -f {} \;

install: install-target install-locale

install_no_locale: install-target

install-target: make-install-dirs
	install -p -m 644 exaile.py $(EXAILELIBDIR)
	-install -p -m 644 xl/*.py[co] $(EXAILELIBDIR)/xl
	install -p -m 644 xl/*.py $(EXAILELIBDIR)/xl
	-install -p -m 644 xl/externals/*.py[co] $(EXAILELIBDIR)/xl/externals
	install -p -m 644 xl/externals/*.py $(EXAILELIBDIR)/xl/externals
	-install -p -m 644 xl/metadata/*.py[co] $(EXAILELIBDIR)/xl/metadata
	install -p -m 644 xl/metadata/*.py $(EXAILELIBDIR)/xl/metadata
	-install -p -m 644 xl/player/*.py[co] $(EXAILELIBDIR)/xl/player
	install -p -m 644 xl/player/*.py $(EXAILELIBDIR)/xl/player
	-install -p -m 644 xl/player/gst/*.py[co] $(EXAILELIBDIR)/xl/player/gst
	install -p -m 644 xl/player/gst/*.py $(EXAILELIBDIR)/xl/player/gst
	-install -p -m 644 xl/migrations/*.py[co] $(EXAILELIBDIR)/xl/migrations
	install -p -m 644 xl/migrations/*.py $(EXAILELIBDIR)/xl/migrations
	-install -p -m 644 xl/migrations/database/*.py[co] $(EXAILELIBDIR)/xl/migrations/database/
	install -p -m 644 xl/migrations/database/*.py $(EXAILELIBDIR)/xl/migrations/database/
	-install -p -m 644 xl/migrations/settings/*.py[co] $(EXAILELIBDIR)/xl/migrations/settings/
	install -p -m 644 xl/migrations/settings/*.py $(EXAILELIBDIR)/xl/migrations/settings/
	-install -p -m 644 xl/trax/*.py[co] $(EXAILELIBDIR)/xl/trax
	install -p -m 644 xl/trax/*.py $(EXAILELIBDIR)/xl/trax
	-install -p -m 644 xlgui/*.py[co] $(EXAILELIBDIR)/xlgui
	install -p -m 644 xlgui/*.py $(EXAILELIBDIR)/xlgui
	-install -p -m 644 xlgui/panel/*.py[co] $(EXAILELIBDIR)/xlgui/panel
	install -p -m 644 xlgui/panel/*.py $(EXAILELIBDIR)/xlgui/panel
	-install -p -m 644 xlgui/preferences/*.py[co] $(EXAILELIBDIR)/xlgui/preferences
	install -p -m 644 xlgui/preferences/*.py $(EXAILELIBDIR)/xlgui/preferences
	-install -p -m 644 xlgui/widgets/*.py[co] $(EXAILELIBDIR)/xlgui/widgets
	install -p -m 644 xlgui/widgets/*.py $(EXAILELIBDIR)/xlgui/widgets
	install -p -m 644 data/images/16x16/*.png $(EXAILESHAREDIR)/data/images/16x16
	install -p -m 644 data/images/22x22/*.png $(EXAILESHAREDIR)/data/images/22x22
	install -p -m 644 data/images/24x24/*.png $(EXAILESHAREDIR)/data/images/24x24
	install -p -m 644 data/images/32x32/*.png $(EXAILESHAREDIR)/data/images/32x32
	install -p -m 644 data/images/48x48/*.png $(EXAILESHAREDIR)/data/images/48x48
	install -p -m 644 data/images/128x128/*.png $(EXAILESHAREDIR)/data/images/128x128
	install -p -m 644 data/images/scalable/*.svg $(EXAILESHAREDIR)/data/images/scalable
	install -p -m 644 data/images/*.png $(EXAILESHAREDIR)/data/images
	install -p -m 644 data/images/128x128/exaile.png \
		$(DESTDIR)$(DATADIR)/pixmaps/exaile.png
	install -p -m 644 data/ui/*.ui $(EXAILESHAREDIR)/data/ui
	install -p -m 644 data/ui/panel/*.ui $(EXAILESHAREDIR)/data/ui/panel
	install -p -m 644 data/ui/preferences/*.ui $(EXAILESHAREDIR)/data/ui/preferences
	install -p -m 644 data/ui/preferences/widgets/*.ui $(EXAILESHAREDIR)/data/ui/preferences/widgets
	install -p -m 644 data/ui/widgets/*.ui $(EXAILESHAREDIR)/data/ui/widgets
	install -p -m 644 data/exaile.desktop \
		$(DESTDIR)$(DATADIR)/applications/
	install -p -m 644 data/exaile.appdata.xml \
		$(DESTDIR)$(DATADIR)/appdata/
	-install -p -m 644 build/exaile.1.gz $(EXAILEMANDIR)/man1/
	-install -p -m 644 build/exaile.bash-completion $(DESTDIR)$(BASHCOMPDIR)/exaile
	-install -p -m 644 build/exaile.fish-completion $(DESTDIR)$(FISHCOMPDIR)/exaile.fish
	install -p -m 644 data/config/settings.ini $(EXAILECONFDIR)
	tools/generate-launcher "$(DESTDIR)" "$(PREFIX)" "$(EPREFIX)" "$(LIBINSTALLDIR)" \
		"$(PYTHON3_CMD)" && \
	  chmod 755 $(EXAILEBINDIR)/exaile
	sed "s|\@bindir\@|$(EPREFIX)/bin|" data/org.exaile.Exaile.service.in > \
		$(DESTDIR)$(DATADIR)/dbus-1/services/org.exaile.Exaile.service && \
		chmod 644 $(DESTDIR)$(DATADIR)/dbus-1/services/org.exaile.Exaile.service
	if [ -d ".git" ]; then \
		sed "s|__version__ = \"devel\"|__version__ = \"$(shell git describe --tags --abbrev=0)\"|" \
			xl/version.py > $(EXAILELIBDIR)/xl/version.py; \
	fi
	$(MAKE) -C plugins install


# List a *.mo file for any *.po file
LOCALE_SRCS=$(wildcard po/*.po)
LOCALE_OBJS=$(LOCALE_SRCS:.po=.mo)

%.mo: %.po po/messages.pot
	$(eval LOCALE_DIR := `echo $< | sed "s|^po/|build/locale/|" | sed "s|.po|/LC_MESSAGES|"`)
	mkdir -p $(LOCALE_DIR)
	-msgmerge -q -o - $< po/messages.pot | msgfmt -c -o $(LOCALE_DIR)/exaile.mo -

locale: builddir $(LOCALE_OBJS)

install-locale:
	for f in `find build/locale -name exaile.mo` ; do \
	  install -d -m 755 \
	    `echo $$f | sed "s|^build|$(DESTDIR)$(DATADIR)|" | \
	      xargs dirname` && \
	  install -p -m 644 $$f \
	    `echo $$f | sed "s|^build|$(DESTDIR)$(DATADIR)|"` ; \
	  done


plugins_dist:
	$(MAKE) -C plugins dist

manpage: builddir
	LC_ALL=C help2man -n "music manager and player" -N ./exaile \
	  | gzip -9 > build/exaile.1.gz

completion: builddir
	$(PYTHON3_CMD) tools/generate-completion.py bash > build/exaile.bash-completion
	$(PYTHON3_CMD) tools/generate-completion.py fish > build/exaile.fish-completion

clean:
	-find . -name "*.~[0-9]~" -exec rm -f {} \;
	-find . -name "*.py[co]" -exec rm -f {} \;
	rm -rf build/
	$(MAKE) -C plugins clean
	-$(MAKE) -C doc clean
	# for older versions of this Makefile:
	find po/* -depth -type d -exec rm -r {} \;

po/messages.pot: pot

# The "set -o pipefail" makes the whole thing die if any of the find fails.
#   dash (Debian's /bin/sh) doesn't support it and exits immediately, so we test it in a subshell.
# The "export LC_ALL=C" disables any locale-dependent sort behavior.
pot:
	( ( set -o pipefail 2> /dev/null ) && set -o pipefail ; \
	  export LC_ALL=C && cd po && \
	  { find ../xl ../xlgui -name "*.py" | sort && \
	    find ../data/ui -name "*.ui" | sort && \
	    find ../plugins -name "*.py" | sort && \
	    find ../plugins -name "*.ui" | sort ; } \
	  | xgettext --files-from=- --output=messages.pot --from-code=UTF-8 --add-comments=TRANSLATORS --keyword=N_ && \
	  find ../plugins -name PLUGININFO | sort \
	  | xgettext --files-from=- --output=messages.pot --from-code=UTF-8 --add-comments=TRANSLATORS --join-existing --language=Python )
	find po -name '*.po' -exec \
	  msgmerge --previous --update {} po/messages.pot \;

potball: builddir
	tar --bzip2 --format=posix -cf build/exaile-po.tar.bz2 po/ \
	    --transform s/po/./

dist:
	mkdir -p dist
	rm -rf dist/copy
	git archive HEAD --prefix=copy/ | tar -x -C dist
	./tools/dist.sh
	rm -rf dist/copy

check-doc: clean
	$(MAKE) -C doc html

BUILD_DIR		= /tmp/exaile-test-build
test_compile:
	mkdir -p $(BUILD_DIR)
	cp --recursive xl xlgui plugins tools Makefile $(BUILD_DIR)
	$(MAKE) -C $(BUILD_DIR) all

test:
	EXAILE_DIR=$(shell pwd) LC_ALL=C PYTHONPATH=$(shell pwd) $(PYTEST) tests

test_coverage:
	rm -rf coverage/
	rm -f .coverage
	EXAILE_DIR=$(shell pwd) nosetests -w tests --with-coverage --cover-package=xl; \
	mkdir -p coverage; \
	coverage html -d coverage

lint_errors:
	-pylint -e --rcfile tools/pylint.cfg xl xlgui 2> /dev/null

sanitycheck: lint_errors test

format:
	$(BLACK) -S *.py plugins/ xl/ xlgui/ tests/

check_format:
	$(BLACK) --check --diff -S *.py plugins/ xl/ xlgui/ tests/
