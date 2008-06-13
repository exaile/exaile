

clean:
	find . -name "*.py[co]" -exec rm -f {} \;

doc: docclean
	mkdir -p ./doc/
	epydoc -n Exaile -vo ./doc/ --html xl xlgui
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
