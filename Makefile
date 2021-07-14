PY=python3
TEST=test.py

test:
	rm -rf test-temp
	. venv-$(PY)/bin/activate; $(PY) -u -m nose --rednose --verbosity 2 --nocapture $(TEST); deactivate

install-dev:
	$(PY) -m venv venv-$(PY)
	. venv-$(PY)/bin/activate; $(PY) -m pip install nose rednose requests; deactivate

package: uploadserver/__init__.py uploadserver/__main__.py LICENSE README.md setup.py
	$(PY) -m pip install --user --upgrade setuptools wheel
	$(PY) setup.py sdist bdist_wheel

upload: dist/*
	$(PY) -m pip install --user --upgrade twine
	$(PY) -m twine upload dist/*

clean:
	rm -rf build dist uploadserver/__pycache__ uploadserver.egg-info
