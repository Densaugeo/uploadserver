package: uploadserver/__init__.py uploadserver/__main__.py LICENSE README.md setup.py
	python3 -m pip install --user --upgrade setuptools wheel
	python3 setup.py sdist bdist_wheel

upload: dist/*
	python3 -m pip install --user --upgrade twine
	python3 -m twine upload dist/*

clean:
	rm -rf build dist uploadserver/__pycache__ uploadserver.egg-info
