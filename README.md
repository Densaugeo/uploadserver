# uploadserver

Python's http.server extended to include a file upload page

[![License: MIT](https://img.shields.io/badge/license-MIT-blue.svg)](https://mit-license.org/)
[![Build Status](https://travis-ci.com/Densaugeo/uploadserver.svg?branch=master)](https://travis-ci.com/github/Densaugeo/uploadserver)

## Supported Platforms

| Platform | Supported? | Notes |
|-|-|-|
| Python 3.8+ | Yes | Tested on 3.8 through 3.12 every release. |
| Python 3.6-3.7 | No | Was supported by previous versions. |
| Python 3.5- | No | |
| Linux | Yes | Tested on Fedora and Ubuntu every release. |
| Windows | Yes | Occasional manual testing. Haven't noticed any obvious problems. |
| Mac | No idea | I don't have a Mac. Idk if it works or not. |

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

Warning: This is an upload server, and running it will allow uploads.

Now supports uploading multiple files at once! Select multiple files in the web page's file selector, or upload with cURL:
~~~
curl -X POST http://127.0.0.1:8000/upload -F 'files=@multiple-example-1.txt' -F 'files=@multiple-example-2.txt'
~~~

## Basic Authentication (downloads and uploads)

~~~
python3 -m uploadserver --basic-auth hello:world
~~~

Now you can upload with basic authentication. For example:
~~~
curl -X POST http://127.0.0.1:8000/upload -F 'files=@basicauth-example.txt' -u hello:world
~~~

Uploads without authentication will be rejected. Note that basic authentication credentials can be stolen if sent over plain HTTP, so this option is best used with HTTPS.

The server checks credentials before it handles the body of the request, so this mode of operation is not susceptible to DoS attack mentioned in the previous section.

## Basic Authentication (uploads only)

~~~
python3 -m uploadserver --basic-auth-upload hello:world
~~~

The same as above, but authentication is only required for upload operations.

If both --basic-auth and --basic-auth-upload are specified, first one will be used for downloads and the second one for uploads.

## Theme Option

The upload page supports a dark mode for showing white text on black background. If no option is specified, the color scheme is chosen from the client’s browser’s preference (which typically matches their operating system’s setting, if light or dark mode is supported by the OS). To enforce the light or dark theme, the CLI parameter `--theme` can be used:
~~~
python3 -m uploadserver --theme light
~~~
or
~~~
python3 -m uploadserver --theme dark
~~~

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

## Breaking Changes in 5.0.0

- Support for Python 3.6-7 dropped.
- `--token` option removed (use `--basic-auth` or `--basic-auth-upload` instead).

## Breaking Changes in 4.0.0

- By default, uploaded files which have the same name as an existing file are renamed. To restore the previous behavior of overwriting them, pass `--allowreplace`.
- File uploads with no files in them are rejected with 400 Bad Request instead of 500 Internal Server Error, with a more informative error message.
- Handling of large uploads has been improved. Theoretically this should not cause any breaking changes, but filesystems are black magic and should be viewed with suspicion.

## Breaking Changes in 3.0.0

- If `serve_forever` is called directly, such as by an extension, the `theme` field is now required on the arguments object. This change will not affect users who run this module unmodified.

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

Thanks to marvinruder for work on the upload progress indicator, theme option, and pre-validation of tokens before upload.

Thanks to shuangye for finding an easy way to handle large file uploads, and improved handling of filename collisions.

Thanks to abbbe for adding HTTP basic auth (has now replaced the token option).
