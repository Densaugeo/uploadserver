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

Run with a simple token.
~~~
python3 -m uploadserver -t helloworld
~~~

Now you can upload a file with token. For example:
`curl http://127.0.0.1:8000/upload -F "file_1=@abc.txt" -F 'token=helloworld'`

Run with HTTPS:
~~~
# Generate self-signed certificate
openssl req -x509 -out localhost.pem -keyout localhost.pem -newkey rsa:2048 -nodes -sha256 -subj '/CN=localhost'

python3 -m uploadserver -c localhost.pem
~~~

Note: This uses a self-signed certificate which clients such as web browser and cURL will warn about. Most browsers will allow you to proceed after adding an exception, and cURL will work if given the -k option. Using your own certificate from a certificate authority will avoid these warnings.

## Credits

Most of `uploadserver/__main__.py` was copied from Python's `http.server.main()`.
