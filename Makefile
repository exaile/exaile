
all: compile doc
	@echo "Ready to install... except there's no install rule yet :P"

compile:
	python -m compileall xl lib xlgui
	python -O -m compileall xl lib xlgui

plugins:
	cd plugins && make dist && cd ..

clean:
	find . -name "*.py[co]" -exec rm -f {} \;
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
