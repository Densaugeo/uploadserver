PY=python3
TEST=test.py
PYTEST_ARGS=--verbosity 2 --tb short
VERBOSE=1
PROTOCOL=HTTP

ifneq ($(VERBOSE), 0)
	PYTEST_ARGS:=$(PYTEST_ARGS) --capture no
endif

test-all: server.pem client.pem client.crt
	./test-all.sh

test: server.pem client.pem client.crt
	rm -rf test-temp
	. venv-$(PY)/bin/activate; PROTOCOL=$(PROTOCOL) VERBOSE=$(VERBOSE) $(PY) -u -m pytest $(PYTEST_ARGS) $(TEST)

test-travis: server.pem client.pem client.crt
	rm -rf test-temp
	PROTOCOL=HTTP VERBOSE=0 python -u -m pytest --tb short test.py
	rm -rf test-temp
	PROTOCOL=HTTPS VERBOSE=0 python -u -m pytest --tb short test.py

install-dev:
	chmod 775 test-all.sh
	$(PY) -m venv venv-$(PY)
	. venv-$(PY)/bin/activate; $(PY) -m pip install pytest requests

server.pem:
	openssl req -x509 -out server.pem -keyout server.pem -newkey rsa:3072 \
		-nodes -sha256 -subj '/CN=server' -days 10000

client.pem:
	openssl req -x509 -out client.pem -keyout client.pem -newkey rsa:3072 \
		-nodes -sha256 -subj '/CN=client' -days 10000

client.crt:
	openssl x509 -in client.pem -out client.crt

package: uploadserver/__init__.py uploadserver/__main__.py LICENSE README.md setup.py
	$(PY) -m pip install --user --upgrade setuptools wheel
	$(PY) setup.py sdist bdist_wheel

upload: dist/*
	$(PY) -m pip install --user --upgrade twine
	$(PY) -m twine upload dist/*
	# Remove keyring, otherwise it will nag about passwords every time I use pip
	$(PY) -m pip uninstall -y keyring

clean:
	rm -rf build dist uploadserver/__pycache__ uploadserver.egg-info __pycache__ test-temp server.pem client.pem client.crt
