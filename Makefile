.PHONY: build clean test

build:
	python setup.py build_ext -i && python setup.py develop

clean:
	git clean -dfX

test:
	python -m numba.runtests -m 12
