PY=python3
TEST=test.py
PYTEST_ARGS=--verbosity 2
VERBOSE=1
PROTOCOL=HTTP

ifneq ($(VERBOSE), 0)
	PYTEST_ARGS:=$(PYTEST_ARGS) --capture no
endif

test-all:
	./test-all.sh

test: localhost.pem
	rm -rf test-temp
	. venv-$(PY)/bin/activate; PROTOCOL=$(PROTOCOL) VERBOSE=$(VERBOSE) $(PY) -u -m pytest $(PYTEST_ARGS) $(TEST)

test-travis:
	rm -rf test-temp
	PROTOCOL=HTTP VERBOSE=0 python -u -m pytest test.py
	rm -rf test-temp
	PROTOCOL=HTTPS VERBOSE=0 python -u -m pytest test.py

install-dev:
	chmod 775 test-all.sh
	$(PY) -m venv venv-$(PY)
	. venv-$(PY)/bin/activate; $(PY) -m pip install pytest requests

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
