PREFIX ?= /usr/local
FIREFOX ?= /usr/lib/firefox

all: build 
	@echo "Done"
	@echo "Type: 'make install' now"

build: mmkeys.so
	python -m compileall xl lib

mmkeys.so:
	cd mmkeys && make mmkeys.so && cd ..
	cp mmkeys/mmkeys.so .

make-install-dirs: 
	mkdir -p $(DESTDIR)$(PREFIX)/bin
	mkdir -p $(DESTDIR)$(PREFIX)/lib/
	mkdir -p $(DESTDIR)$(PREFIX)/lib/exaile
	mkdir -p $(DESTDIR)$(PREFIX)/share/
	mkdir -p $(DESTDIR)$(PREFIX)/share/pixmaps
	mkdir -p $(DESTDIR)$(PREFIX)/share/applications
	mkdir -p $(DESTDIR)$(PREFIX)/share/exaile
	mkdir -p $(DESTDIR)$(PREFIX)/share/exaile/images
	mkdir -p $(DESTDIR)$(PREFIX)/share/exaile/plugins
	mkdir -p $(DESTDIR)$(PREFIX)/share/exaile/images/default_theme
	mkdir -p $(DESTDIR)$(PREFIX)/share/exaile/xl
	mkdir -p $(DESTDIR)$(PREFIX)/share/exaile/xl/media
	mkdir -p $(DESTDIR)$(PREFIX)/share/exaile/lib
	mkdir -p $(DESTDIR)$(PREFIX)/share/exaile/sql
	mkdir -p $(DESTDIR)$(PREFIX)/share/locale

install: make-install-dirs mmkeys.so
	install -m 644 exaile.py $(DESTDIR)$(PREFIX)/share/exaile
	install -m 644 exaile.glade $(DESTDIR)$(PREFIX)/share/exaile
	install -m 644 equalizer.ini $(DESTDIR)$(PREFIX)/share/exaile
	install -m 644 sql/*.sql $(DESTDIR)$(PREFIX)/share/exaile/sql
	install -m 644 mmkeys.so $(DESTDIR)$(PREFIX)/lib/exaile
	install -m 644 images/*.png $(DESTDIR)$(PREFIX)/share/exaile/images
	install -m 644 images/default_theme/*.png \
	$(DESTDIR)$(PREFIX)/share/exaile/images/default_theme
	install -m 644 xl/*.py $(DESTDIR)$(PREFIX)/share/exaile/xl
	install -m 644 xl/*.pyc $(DESTDIR)$(PREFIX)/share/exaile/xl
	install -m 644 xl/media/*.py $(DESTDIR)$(PREFIX)/share/exaile/xl/media
	install -m 644 xl/media/*.pyc $(DESTDIR)$(PREFIX)/share/exaile/xl/media
	install -m 644 lib/*.py $(DESTDIR)$(PREFIX)/share/exaile/lib
	install -m 644 lib/*.pyc $(DESTDIR)$(PREFIX)/share/exaile/lib
	install -m 644 plugins/*.py $(DESTDIR)$(PREFIX)/share/exaile/plugins
	install -m 644 plugins/*.glade $(DESTDIR)$(PREFIX)/share/exaile/plugins
	install -m 644 images/largeicon.png \
	$(DESTDIR)$(PREFIX)/share/pixmaps/exaile.png
	install -m 644 exaile.desktop $(DESTDIR)$(PREFIX)/share/applications/
	cd $(DESTDIR)$(PREFIX)/bin && \
	  /bin/echo -e \
	    "#!/bin/sh\n" \
	    "cd $(PREFIX)/share/exaile\n" \
	    "export LD_LIBRARY_PATH=\$$LD_LIBRARY_PATH:$(FIREFOX)\n" \
	    "exec python exaile.py \"\$$@\"" \
	    > exaile && \
	  chmod 755 exaile
	for f in `find po -name exaile.mo` ; do \
	  install -D $$f \
	    `echo $$f | sed "s|po|$(DESTDIR)$(PREFIX)/share/locale|"` ; \
	  done

clean:
	-rm mmkeys.so
	cd mmkeys && make clean && cd ..
	find . -name "*.pyc" -exec rm {} \;
	find . -name "*.pyo" -exec rm {} \;

tarball: clean
	tar --exclude .svn -czvf ../exaile.tar.gz ../exaile
	
uninstall:
	rm -r $(DESTDIR)$(PREFIX)/share/exaile
	rm -r $(DESTDIR)$(PREFIX)/lib/exaile
	rm -r $(DESTDIR)$(PREFIX)/bin/exaile
	rm  $(DESTDIR)$(PREFIX)/share/applications/exaile.desktop
	rm  $(DESTDIR)$(PREFIX)/share/pixmaps/exaile.png
	find $(DESTDIR)$(PREFIX)/share/locale -name exaile.mo -exec rm {} \;
