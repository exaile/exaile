PREFIX ?= /usr/local
LIBDIR ?= /lib
FIREFOX ?= /usr/lib/firefox

all: compile mmkeys.so translations
	@echo "Done"
	@echo "Type: 'make install' now"

compile:
	python -m compileall xl lib
	python -O -m compileall xl lib

mmkeys.so:
	cd mmkeys && make mmkeys.so && cd .. && cp mmkeys/mmkeys.so .

translations:
	python po/createpot.py compile

make-install-dirs: 
	mkdir -p $(DESTDIR)$(PREFIX)/bin
	mkdir -p $(DESTDIR)$(PREFIX)$(LIBDIR)
	mkdir -p $(DESTDIR)$(PREFIX)$(LIBDIR)/exaile
	mkdir -p $(DESTDIR)$(PREFIX)$(LIBDIR)/exaile/lib
	mkdir -p $(DESTDIR)$(PREFIX)$(LIBDIR)/exaile/xl
	mkdir -p $(DESTDIR)$(PREFIX)$(LIBDIR)/exaile/xl/gui
	mkdir -p $(DESTDIR)$(PREFIX)$(LIBDIR)/exaile/xl/media
	mkdir -p $(DESTDIR)$(PREFIX)$(LIBDIR)/exaile/xl/panels
	mkdir -p $(DESTDIR)$(PREFIX)$(LIBDIR)/exaile/xl/plugins
	mkdir -p $(DESTDIR)$(PREFIX)/share/
	mkdir -p $(DESTDIR)$(PREFIX)/share/pixmaps
	mkdir -p $(DESTDIR)$(PREFIX)/share/applications
	mkdir -p $(DESTDIR)$(PREFIX)/share/exaile
	mkdir -p $(DESTDIR)$(PREFIX)/share/exaile/images
	mkdir -p $(DESTDIR)$(PREFIX)/share/exaile/images/default_theme
	mkdir -p $(DESTDIR)$(PREFIX)/share/exaile/data
	mkdir -p $(DESTDIR)$(PREFIX)/share/exaile/sql
	mkdir -p $(DESTDIR)$(PREFIX)/share/exaile/xl
	mkdir -p $(DESTDIR)$(PREFIX)/share/exaile/xl/plugins
	mkdir -p $(DESTDIR)$(PREFIX)/share/locale
	mkdir -p $(DESTDIR)$(PREFIX)/share/man/man1

install: make-install-dirs
	install -m 644 exaile.1 $(DESTDIR)$(PREFIX)/share/man/man1
	install -m 644 exaile.py $(DESTDIR)$(PREFIX)$(LIBDIR)/exaile
	install -m 644 exaile.glade $(DESTDIR)$(PREFIX)/share/exaile
	install -m 644 equalizer.ini $(DESTDIR)$(PREFIX)/share/exaile
	install -m 644 sql/*.sql $(DESTDIR)$(PREFIX)/share/exaile/sql
	-install -m 644 mmkeys.so $(DESTDIR)$(PREFIX)$(LIBDIR)/exaile
	install -m 644 images/*.png $(DESTDIR)$(PREFIX)/share/exaile/images
	install -m 644 images/default_theme/*.png \
	$(DESTDIR)$(PREFIX)/share/exaile/images/default_theme
	install -m 644 xl/*.py $(DESTDIR)$(PREFIX)$(LIBDIR)/exaile/xl
	-install -m 644 xl/*.py[co] $(DESTDIR)$(PREFIX)$(LIBDIR)/exaile/xl
	install -m 644 xl/media/*.py $(DESTDIR)$(PREFIX)$(LIBDIR)/exaile/xl/media
	-install -m 644 xl/media/*.py[co] $(DESTDIR)$(PREFIX)$(LIBDIR)/exaile/xl/media
	install -m 644 xl/panels/*.py $(DESTDIR)$(PREFIX)$(LIBDIR)/exaile/xl/panels
	-install -m 644 xl/panels/*.py[co] $(DESTDIR)$(PREFIX)$(LIBDIR)/exaile/xl/panels
	install -m 644 xl/gui/*.py $(DESTDIR)$(PREFIX)$(LIBDIR)/exaile/xl/gui
	-install -m 644 xl/gui/*.py[co] $(DESTDIR)$(PREFIX)$(LIBDIR)/exaile/xl/gui
	install -m 644 lib/*.py $(DESTDIR)$(PREFIX)$(LIBDIR)/exaile/lib
	-install -m 644 lib/*.py[co] $(DESTDIR)$(PREFIX)$(LIBDIR)/exaile/lib
	install -m 644 data/*.ini $(DESTDIR)$(PREFIX)/share/exaile/data
	install -m 644 xl/plugins/*.py $(DESTDIR)$(PREFIX)$(LIBDIR)/exaile/xl/plugins
	install -m 644 xl/plugins/*.glade $(DESTDIR)$(PREFIX)/share/exaile/xl/plugins
	install -m 644 images/largeicon.png \
	$(DESTDIR)$(PREFIX)/share/pixmaps/exaile.png
	install -m 644 exaile.desktop $(DESTDIR)$(PREFIX)/share/applications/
	cd $(DESTDIR)$(PREFIX)/bin && \
	  /bin/echo -e \
	    "#!/bin/sh\n" \
	    "cd $(PREFIX)/share/exaile\n" \
	    "export LD_LIBRARY_PATH=\$$LD_LIBRARY_PATH:$(FIREFOX)\n" \
		"export MOZILLA_FIVE_HOME=$(firefox)\n" \
	    "exec python $(PREFIX)$(LIBDIR)/exaile/exaile.py \"\$$@\"" \
	    > exaile && \
	  chmod 755 exaile
	for f in `find po -name exaile.mo` ; do \
	  install -d -m 755 \
	    `echo $$f | sed "s|^po|$(DESTDIR)$(PREFIX)/share/locale|" | \
	      xargs dirname` && \
	  install -m 644 $$f \
	    `echo $$f | sed "s|^po|$(DESTDIR)$(PREFIX)/share/locale|"` ; \
	  done

clean:
	rm -f mmkeys.so
	cd mmkeys && make clean && cd ..
	find . -name "*.py[co]" -exec rm -f {} \;
	find po -maxdepth 1 -regextype posix-basic -regex "po/[^.]*" -type d -exec rm -rf {} \;
	rm -f exaile.glade.h messages.pot plugins/plugins.glade.h

tarball: clean
	tar --exclude .svn -czvf ../exaile.tar.gz ../exaile

uninstall:
	rm -rf $(DESTDIR)$(PREFIX)/share/exaile
	rm -rf $(DESTDIR)$(PREFIX)$(LIBDIR)/exaile
	rm -rf $(DESTDIR)$(PREFIX)/bin/exaile
	rm -f $(DESTDIR)$(PREFIX)/share/applications/exaile.desktop
	rm -f $(DESTDIR)$(PREFIX)/share/pixmaps/exaile.png
	find $(DESTDIR)$(PREFIX)/share/locale -name exaile.mo -exec rm -f {} \;
