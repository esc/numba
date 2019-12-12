.PHONY: build clean test

deps:
	conda install  -c numba/label/dev llvmlite
	conda install numpy pyyaml colorama scipy jinja2 cffi ipython

build:
	python setup.py build_ext -i && python setup.py develop

clean:
	git clean -dfX

test:
	python -m numba.runtests -m 12
