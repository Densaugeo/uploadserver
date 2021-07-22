PY=python3
TEST=test.py
NOSE_ARGS=--rednose --verbosity 2
VERBOSE=1
PROTOCOL=HTTP

ifneq ($(VERBOSE), 0)
	NOSE_ARGS:=$(NOSE_ARGS) --nocapture
endif

test-all:
	./test-all.sh

test: localhost.pem
	rm -rf test-temp
	. venv-$(PY)/bin/activate; PROTOCOL=$(PROTOCOL) VERBOSE=$(VERBOSE) $(PY) -u -m nose $(NOSE_ARGS) $(TEST); deactivate

install-dev:
	chmod 775 test-all.sh
	$(PY) -m venv venv-$(PY)
	. venv-$(PY)/bin/activate; $(PY) -m pip install nose rednose requests; deactivate

localhost.pem:
	openssl req -x509 -out localhost.pem -keyout localhost.pem -newkey rsa:2048 -nodes -sha256 -subj '/CN=localhost'

package: uploadserver/__init__.py uploadserver/__main__.py LICENSE README.md setup.py
	$(PY) -m pip install --user --upgrade setuptools wheel
	$(PY) setup.py sdist bdist_wheel

upload: dist/*
	$(PY) -m pip install --user --upgrade twine
	$(PY) -m twine upload dist/*

clean:
	rm -rf build dist uploadserver/__pycache__ uploadserver.egg-info __pycache__ test-temp
