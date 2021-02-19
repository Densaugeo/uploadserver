# uploadserver

Python's http.server extended to include a file upload page

[![License: MIT](https://img.shields.io/badge/license-MIT-blue.svg)](https://mit-license.org/)

## Installation

~~~
python3 -m pip install uploadserver
~~~

May require sudo depending on your distro.

## Usage

~~~
python3 -m uploadserver
~~~

Accepts the same options as [http.server](https://docs.python.org/3/library/http.server.html).

After the server starts, the upload page is at /upload. For example, if the server is running at http://localhost:8000/ go to http://localhost:8000/upload .

Warning: This is an upload server, and running it will allow uploads. Uploaded files will replace existing files with the same name.

## Credits

Most of `uploadserver/__main__.py` was copied from Python's `http.server.main()`.
