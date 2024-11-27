import http.server, http, pathlib, sys, argparse, ssl, os, builtins, tempfile
import base64, binascii, functools, contextlib

# Does not seem to do be used, but leaving this import out causes uploadserver
# to not receive IPv4 requests when started with default options under Windows
import socket

# The cgi module was deprecated in Python 3.13, so I saved a copy in this
# project
if sys.version_info.major == 3 and sys.version_info.minor < 13:
    import cgi
else:
    import uploadserver.cgi

COLOR_SCHEME = {
    'light': 'light',
    'auto': 'light dark',
    'dark': 'dark',
}

def get_upload_page(theme: str) -> bytes:
    return bytes('''<!DOCTYPE html>
<html>
<head>
<title>File Upload</title>
<meta name="viewport" content="width=device-width, user-scalable=no" />
<meta name="color-scheme" content="''' + COLOR_SCHEME.get(theme) + '''">
</head>
<body>
<h1>File Upload</h1>
<form action="upload" method="POST" enctype="multipart/form-data">
<input name="files" type="file" multiple />
<br />
<br />
<input type="submit" />
</form>
<p id="task"></p>
<p id="status"></p>
</body>
<script>
document.getElementsByTagName('form')[0].addEventListener('submit', async e => {
  e.preventDefault()
  
  const uploadFormData = new FormData(e.target)
  const filenames = uploadFormData.getAll('files').map(v => v.name).join(', ')
  const uploadRequest = new XMLHttpRequest()
  uploadRequest.open(e.target.method, e.target.action)
  uploadRequest.timeout = 3600000
  
  uploadRequest.onreadystatechange = () => {
    if (uploadRequest.readyState === XMLHttpRequest.DONE) {
      let message = `${uploadRequest.status}: ${uploadRequest.statusText}`
      if (uploadRequest.status === 0) message = 'Connection failed'
      if (uploadRequest.status === 204) {
        message = `Success: ${uploadRequest.statusText}`
      }
      document.getElementById('status').textContent = message
    }
  }
  
  uploadRequest.upload.onprogress = e => {
    document.getElementById('status').textContent = (e.loaded === e.total ?
      'Saving…' :
      `${Math.floor(100*e.loaded/e.total)}% ` +
      `[${Math.floor(e.loaded/1024)} / ${Math.floor(e.total/1024)}KiB]`
    )
  }
  
  uploadRequest.send(uploadFormData)
  
  document.getElementById('task').textContent = `Uploading ${filenames}:`
  document.getElementById('status').textContent = '0%'
})
</script>
</html>''', 'utf-8')

def get_directory_head_injection(theme: str) -> bytes:
    return bytes('''<!-- Injected by uploadserver -->
<meta name="viewport" content="width=device-width" />
<meta name="color-scheme" content="''' + COLOR_SCHEME.get(theme) + '''">
<!-- End injection by uploadserver -->
''', 'utf-8')

DIRECTORY_BODY_INJECTION = b'''<!-- Injected by uploadserver -->
<a href="/upload">File upload</a>
(provided by uploadserver, all files go to server root)
<hr>
<!-- End injection by uploadserver -->
'''

def send_upload_page(handler: http.server.BaseHTTPRequestHandler):
    handler.send_response(http.HTTPStatus.OK)
    handler.send_header('Content-Type', 'text/html; charset=utf-8')
    handler.send_header('Content-Length', len(get_upload_page(args.theme)))
    handler.end_headers()
    handler.wfile.write(get_upload_page(args.theme))

class PersistentFieldStorage(cgi.FieldStorage):
    # Override cgi.FieldStorage.make_file() method. Valid for Python 3.1 ~ 3.10.
    # Modified version of the original .make_file() method (base copied from
    # Python 3.10)
    def make_file(self) -> object:
        if self._binary_file:
            return tempfile.NamedTemporaryFile(mode = 'wb+',
                dir = args.directory, delete = False)
        else:
            return tempfile.NamedTemporaryFile("w+", dir = args.directory,
                delete = False, encoding = self.encoding, newline = '\n')

# True argument/return type is str | pathlib.Path, but Python 3.9 doesn't
# support |
def auto_rename(path: pathlib.Path) -> pathlib.Path:
    if not os.path.exists(path):
        return path
    (base, ext) = os.path.splitext(path)
    for i in range(1, sys.maxsize):
        renamed_path = f'{base} ({i}){ext}'
        if not os.path.exists(renamed_path):
            return renamed_path
    raise FileExistsError(f'File {path} already exists.')

def receive_upload(handler: http.server.BaseHTTPRequestHandler,
) -> tuple[http.HTTPStatus, str]:
    result = (http.HTTPStatus.INTERNAL_SERVER_ERROR, 'Server error')
    name_conflict = False
    
    form = PersistentFieldStorage(fp=handler.rfile, headers=handler.headers,
        environ={'REQUEST_METHOD': 'POST'})
    if 'files' not in form:
        return (http.HTTPStatus.BAD_REQUEST, 'Field "files" not found')
    
    fields = form['files']
    if not isinstance(fields, list):
        fields = [fields]
    
    if not all(field.file and field.filename for field in fields):
        return (http.HTTPStatus.BAD_REQUEST, 'No files selected')
    
    for field in fields:
        if field.file and field.filename:
            filename = pathlib.Path(field.filename).name
        else:
            filename = None
        
        if filename:
            destination = pathlib.Path(args.directory) / filename
            if os.path.exists(destination):
                if args.allow_replace and os.path.isfile(destination):
                    os.remove(destination)
                else:
                    destination = auto_rename(destination)
                    name_conflict = True
            if hasattr(field.file, 'name'):
                source = field.file.name
                field.file.close()
                os.rename(source, destination)
            # class '_io.BytesIO', small file (< 1000B, in cgi.py), in-memory
            # buffer
            else:
                with open(destination, 'wb') as f:
                    f.write(field.file.read())
            handler.log_message('[Uploaded] "%s" --> %s', filename, destination)
            result = (http.HTTPStatus.NO_CONTENT, 'Some filename(s) changed '
                'due to name conflict' if name_conflict else 'Files accepted')
    
    return result

# True return type is tuple[bool, str | None], but Python 3.9 doesn't support |
def check_http_authentication_header(
handler: http.server.BaseHTTPRequestHandler, auth: str,
) -> tuple[bool, str]:
    auth_header = handler.headers.get('Authorization')
    if auth_header is None:
        return (False, 'No credentials given')
    
    auth_header_words = auth_header.split(' ')
    if len(auth_header_words) != 2:
        return (False, 'Credentials incorrectly formatted')
    
    if auth_header_words[0].lower() != 'basic':
        return (False, 'Credentials incorrectly formatted')
    
    try:
        http_username_password = base64.b64decode(auth_header_words[1]).decode()
    except binascii.Error:
        return (False, 'Credentials incorrectly formatted')
    
    http_username, http_password = http_username_password.split(':', 2)
    args_username, args_password = auth.split(':', 2)
    if http_username != args_username: return (False, 'Bad username')
    if http_password != args_password: return (False, 'Bad password')
    
    return (True, None)

def check_http_authentication(handler: http.server.BaseHTTPRequestHandler
) -> bool:
    """
    This function should be called in at the beginning of HTTP method handler.
    It validates Authorization header and sends back 401 response on failure.
    It returns False if this happens.
    """
    if not args.basic_auth_upload:
        # If no auth settings apply, check always passes
        if not args.basic_auth:
            return True
        
        # If only --basic-auth is supplied, it's used for all requests
        valid, message = check_http_authentication_header(handler, args.basic_auth)
    else:
        # If --basic-auth-upload is supplied, it's always required for /upload
        if handler.path == '/upload':
            valid, message = check_http_authentication_header(handler,
                args.basic_auth_upload)
        else:
            # For paths outside /upload, no auth is required when --basic-auth
            # is not supplied
            if not args.basic_auth:
                return True
            
            # For paths outise /upload, if both auths are supplied both are
            # accepted
            else:
                valid, message = check_http_authentication_header(handler, args.basic_auth)
                
                if not valid:
                    valid, message = check_http_authentication_header(handler, args.basic_auth_upload)
    
    if not valid:
        handler.log_message('Request rejected (%s)', message)
        handler.send_response(http.HTTPStatus.UNAUTHORIZED, message)
        handler.send_header('WWW-Authenticate', 'Basic realm="uploadserver"')
        handler.end_headers()
    
    return valid

# Let's not inherit http.server.SimpleHTTPRequestHandler - that would cause
# diamond-pattern inheritance
class ListDirectoryInterception:
    # Only runs when serving directory listings
    def flush_headers_interceptor(self):
        for i, header in enumerate(self._headers_buffer):
            if header[:15] == b'Content-Length:':
                length = int(header[15:]) + len(DIRECTORY_BODY_INJECTION) + \
                    len(get_directory_head_injection(args.theme))
                
                # Use same encoding that self.send_header() uses
                self._headers_buffer[i] = f'Content-Length: {length}\r\n' \
                    .encode('latin-1', 'strict')
        
        # Can't use super() - avoiding diamond-pattern inheritance'
        http.server.SimpleHTTPRequestHandler.flush_headers(self)
    
    # Only runs when serving directory listings
    def copyfile_interceptor(self, source, outputfile):
        content = source.read()
        content = content.replace(b'</head>',
            get_directory_head_injection(args.theme) + b'</head>')
        content = content.replace(b'<ul>', DIRECTORY_BODY_INJECTION + b'<ul>')
        outputfile.write(content)
    
    # True argument type is str | pathlib.Path, but Python 3.9 doesn't support |
    def list_directory(self, path: pathlib.Path) -> object:
        setattr(self, 'flush_headers', self.flush_headers_interceptor)
        setattr(self, 'copyfile', self.copyfile_interceptor)
        
        # Can't use super() - avoiding diamond-pattern inheritance'
        return http.server.SimpleHTTPRequestHandler.list_directory(self, path)

class SimpleHTTPRequestHandler(ListDirectoryInterception,
    http.server.SimpleHTTPRequestHandler):
    def do_GET(self):
        if not check_http_authentication(self): return
        
        if self.path == '/upload':
            send_upload_page(self)
        else:
            super().do_GET()
    
    def do_POST(self):
        if not check_http_authentication(self): return
        
        if self.path == '/upload':
            result = receive_upload(self)
            
            if result[0] < http.HTTPStatus.BAD_REQUEST:
                self.send_response(result[0], result[1])
                self.end_headers()
            else:
                self.send_error(result[0], result[1])
        else:
            self.send_error(http.HTTPStatus.NOT_FOUND,
                'Can only POST/PUT to /upload')
    
    def do_PUT(self):
        self.do_POST()

class CGIHTTPRequestHandler(ListDirectoryInterception,
    http.server.CGIHTTPRequestHandler):
    def do_GET(self):
        if not check_http_authentication(self): return
        
        if self.path == '/upload':
            send_upload_page(self)
        else:
            super().do_GET()
    
    def do_POST(self):
        if not check_http_authentication(self): return
        
        if self.path == '/upload':
            result = receive_upload(self)
            
            if result[0] < http.HTTPStatus.BAD_REQUEST:
                self.send_response(result[0], result[1])
                self.end_headers()
            else:
                self.send_error(result[0], result[1])
        else:
            super().do_POST()
    
    def do_PUT(self):
        self.do_POST()

def intercept_first_print():
    if args.server_certificate:
        # Use the right protocol in the first print call in case of HTTPS
        old_print = builtins.print
        def new_print(*args, **kwargs):
            old_print(args[0].replace('HTTP', 'HTTPS').replace('http', 'https'),
                **kwargs)
            builtins.print = old_print
        builtins.print = new_print

def ssl_wrap(socket: socket.socket) -> ssl.SSLSocket:
    context = ssl.create_default_context(ssl.Purpose.CLIENT_AUTH)
    server_root = pathlib.Path(args.directory).resolve()
    
    # Server certificate handling
    server_certificate = pathlib.Path(args.server_certificate).resolve()
    
    if not server_certificate.is_file():
        print(f'Server certificate "{server_certificate}" not found, exiting')
        sys.exit(4)
    
    if server_root in server_certificate.parents:
        print(f'Server certificate "{server_certificate}" is inside web server '
            f'root "{server_root}", exiting')
        sys.exit(3)
    
    try:
        context.load_cert_chain(certfile=server_certificate)
    except ssl.SSLError as e:
        print(f'Unable to load certificate "{server_certificate}", exiting\n\n'
            f'NOTE: Certificate must be a single file in .pem format. If you '
            'have multiple certificate files, such as Let\'s Encrypt provides, '
            'you can cat them together to get one file.')
        sys.exit(4)
    
    if args.client_certificate:
        # Client certificate handling
        client_certificate = pathlib.Path(args.client_certificate).resolve()
        
        if not client_certificate.is_file():
            print(f'Client certificate "{client_certificate}" not found, '
                'exiting')
            sys.exit(4)
        
        if server_root in client_certificate.parents:
            print(f'Client certificate "{client_certificate}" is inside web '
                f'server root "{server_root}", exiting')
            sys.exit(3)
    
        context.load_verify_locations(cafile=client_certificate)
        context.verify_mode = ssl.CERT_REQUIRED
    
    try:
        return context.wrap_socket(socket, server_side=True)
    except ssl.SSLError as e:
        print('SSL error: "{}", exiting'.format(e))
        sys.exit(5)

def serve_forever():
    # Verify arguments in case the method was called directly
    assert hasattr(args, 'port') and type(args.port) is int
    assert hasattr(args, 'cgi') and type(args.cgi) is bool
    assert hasattr(args, 'allow_replace') and type(args.allow_replace) is bool
    assert hasattr(args, 'bind')
    assert hasattr(args, 'theme')
    assert hasattr(args, 'server_certificate')
    assert hasattr(args, 'client_certificate')
    assert hasattr(args, 'basic_auth')
    assert hasattr(args, 'basic_auth_upload')
    assert hasattr(args, 'directory') and type(args.directory) is str
    
    if args.cgi:
        handler_class = CGIHTTPRequestHandler
    else:
        handler_class = functools.partial(SimpleHTTPRequestHandler,
            directory=args.directory)
    
    print('File upload available at /upload')
    
    class DualStackServer(http.server.ThreadingHTTPServer):
        def server_bind(self):
            # suppress exception when protocol is IPv4
            with contextlib.suppress(Exception):
                self.socket.setsockopt(
                    socket.IPPROTO_IPV6, socket.IPV6_V6ONLY, 0)
            bind = super().server_bind()
            if args.server_certificate:
                self.socket = ssl_wrap(self.socket)
            return bind
    server_class = DualStackServer
    
    intercept_first_print()
    http.server.test(
        HandlerClass=handler_class,
        ServerClass=server_class,
        port=args.port,
        bind=args.bind,
    )

def main():
    global args
    
    parser = argparse.ArgumentParser()
    parser.add_argument('port', type=int, default=8000, nargs='?',
        help='Specify alternate port [default: 8000]')
    parser.add_argument('--cgi', action='store_true',
        help='Run as CGI Server')
    parser.add_argument('--allow-replace', action='store_true', default=False,
        help='Replace existing file if uploaded file has the same name. Auto '
        'rename by default.')
    parser.add_argument('--bind', '-b', metavar='ADDRESS',
        help='Specify alternate bind address [default: all interfaces]')
    parser.add_argument('--directory', '-d', default=os.getcwd(),
        help='Specify alternative directory [default:current directory]')
    parser.add_argument('--theme', type=str, default='auto',
        choices=['light', 'auto', 'dark'],
        help='Specify a light or dark theme for the upload page '
        '[default: auto]')
    parser.add_argument('--server-certificate', '--certificate', '-c',
        help='Specify HTTPS server certificate to use [default: none]')
    parser.add_argument('--client-certificate',
        help='Specify HTTPS client certificate to accept for mutual TLS '
        '[default: none]')
    parser.add_argument('--basic-auth',
        help='Specify user:pass for basic authentication (downloads and '
        'uploads)')
    parser.add_argument('--basic-auth-upload',
        help='Specify user:pass for basic authentication (uploads only)')
    
    args = parser.parse_args()
    if not hasattr(args, 'directory'): args.directory = os.getcwd()
    
    serve_forever()
