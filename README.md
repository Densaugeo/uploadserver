# uploadserver

Python's http.server extended to include a file upload page

[![License: MIT](https://img.shields.io/badge/license-MIT-blue.svg)](https://mit-license.org/)
[![Build Status](https://travis-ci.com/Densaugeo/uploadserver.svg?branch=master)](https://travis-ci.com/github/Densaugeo/uploadserver)

## Installation

~~~
python3 -m pip install --user uploadserver
~~~

## Usage

~~~
python3 -m uploadserver
~~~

Accepts the same options as [http.server](https://docs.python.org/3/library/http.server.html), plus a couple extras (documented below).

After the server starts, the upload page is at /upload. For example, if the server is running at http://localhost:8000/ go to http://localhost:8000/upload .

Warning: This is an upload server, and running it will allow uploads. Uploaded files will replace existing files with the same name.

Now supports uploading multiple files at once! Select multiple files in the web page's file selector, or upload with cURL:
~~~
curl -X POST http://127.0.0.1:8000/upload -F 'files=@multiple-example-1.txt' -F 'files=@multiple-example-2.txt'
~~~

## Token Option

Run with a simple token.
~~~
python3 -m uploadserver -t helloworld
~~~

Now you can upload a file with the token. For example:
~~~
curl -X POST http://127.0.0.1:8000/upload -F 'files=@token-example.txt' -F 'token=helloworld'
~~~

Uploads without the token will be rejected. Tokens can be stolen if sent in plain HTTP, so this option is best used with HTTPS.

## HTTPS Option

Run with HTTPS and without client authentication:
~~~
# Generate self-signed server certificate
openssl req -x509 -out server.pem -keyout server.pem -newkey rsa:2048 -nodes -sha256 -subj '/CN=server'

# The server root should not contain the certificate, for security reasons
cd server-root
python3 -m uploadserver --server-certificate server.pem

# Connect as a client
curl -X POST https://localhost:8000/upload --insecure -F files=@simple-example.txt
~~~

Run with HTTPS and with client authentication:
~~~
# Generate self-signed server certificate
openssl req -x509 -out server.pem -keyout server.pem -newkey rsa:2048 -nodes -sha256 -subj '/CN=server'

# Generate self-signed client certificate
openssl req -x509 -out client.pem -keyout client.pem -newkey rsa:2048 -nodes -sha256 -subj '/CN=client'

# Extract public key from self-signed client certificate
openssl x509 -in client.pem -out client.crt

# The server root should not contain the certificates, for security reasons
cd server-root
python3 -m uploadserver --server-certificate server.pem --client-certificate client.crt

# Connect as a client
curl -X POST https://localhost:8000/upload --insecure --cert client.pem -F files=@mtls-example.txt
~~~

Note: This uses a self-signed server certificate which clients such as web browser and cURL will warn about. Most browsers will allow you to proceed after adding an exception, and cURL will work if given the -k/--insecure option. Using your own certificate from a certificate authority will avoid these warnings.

## Breaking Changes in 2.0.0

- File uploads now respect the `--directory` option. Not doing so was a bug, and a security risk (since it could to the server root containing the server's certificate without the user realizing).
- The `--token` option, if supplied, must be given a value. Not requiring a value was a bug, and a security risk (since a user could specify the token option but forget to provide a token).
- Some internal refactoring was done to support creating extensions. This does not affect command line use.

## Breaking Changes in 1.0.0

- File field in upload form renamed from `file_1` to `files`, to reflect support for multiple file upload. Scripts using cURL will need to be upadted with the new field name.
- Successful uploads now respond with 204 No Content instead of 200 OK, so that cURL will not default to printing the upload page at the terminal.

## Acknowledgements

Much of `main()` was copied from Python's `http.server`.

Thanks to lishoujun for sending the first pull request! (Added the token option.)

Thanks to NteRySin for several improvements including mTLS support and refactoring to support use by other modules.
