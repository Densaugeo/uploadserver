import http.server, http, cgi, pathlib, sys, argparse, ssl, os

if sys.version_info.major > 3 or sys.version_info.minor >= 7:
    import functools

if sys.version_info.major > 3 or sys.version_info.minor >= 8:
    import contextlib

UPLOAD_PAGE = bytes('''<!DOCTYPE html>
<html>
<head>
<title>File Upload</title>
<meta name="viewport" content="width=device-width, user-scalable=no" />
<style type="text/css">
@media (prefers-color-scheme: dark) {
  body {
    background-color: #000;
    color: #fff;
  }
}
</style>
</head>
<body onload="document.getElementsByName('token')[0].value=localStorage.token || ''">
<h1>File Upload</h1>
<form action="upload" method="POST" enctype="multipart/form-data">
<input name="files" type="file" multiple />
<br />
<br />
Token (only needed if server was started with token option): <input name="token" type="text" />
<br />
<br />
<input type="submit" onclick="localStorage.token = document.getElementsByName('token')[0].value" />
</form>
</body>
</html>''', 'utf-8')

def send_upload_page(handler):
    handler.send_response(http.HTTPStatus.OK)
    handler.send_header('Content-Type', 'text/html; charset=utf-8')
    handler.send_header('Content-Length', len(UPLOAD_PAGE))
    handler.end_headers()
    handler.wfile.write(UPLOAD_PAGE)

def receive_upload(handler):
    result = (http.HTTPStatus.INTERNAL_SERVER_ERROR, 'Server error')
    
    form = cgi.FieldStorage(fp=handler.rfile, headers=handler.headers, environ={'REQUEST_METHOD': 'POST'})
    if 'files' not in form:
        return (http.HTTPStatus.BAD_REQUEST, 'Field "files" not found')
    
    fields = form['files']
    if not isinstance(fields, list):
        fields = [fields]
    
    for field in fields:
        if field.file and field.filename:
            filename = pathlib.Path(field.filename).name
        else:
            filename = None
        
        if args.token:
            # server started with token.
            if 'token' not in form or form['token'].value != args.token:
                # no token or token error
                handler.log_message('Upload of "{}" rejected (bad token)'.format(filename))
                result = (http.HTTPStatus.FORBIDDEN, 'Token is enabled on this server, and your token is wrong')
                continue # continue so if a multiple file upload is rejected, each file will be logged
        
        if filename:
            with open(pathlib.Path(args.directory) / filename, 'wb') as f:
                f.write(field.file.read())
                handler.log_message('Upload of "{}" accepted'.format(filename))
                result = (http.HTTPStatus.NO_CONTENT, None)
    
    return result

class SimpleHTTPRequestHandler(http.server.SimpleHTTPRequestHandler):
    def do_GET(self):
        if self.path == '/upload': send_upload_page(self)
        else: http.server.SimpleHTTPRequestHandler.do_GET(self)
    
    def do_POST(self):
        if self.path == '/upload':
            result = receive_upload(self)
            if result[0] < http.HTTPStatus.BAD_REQUEST:
                self.send_response(result[0], result[1])
                self.end_headers()
            else:
                self.send_error(result[0], result[1])
        else:
            self.send_error(http.HTTPStatus.NOT_FOUND, 'Can only POST to /upload')

class CGIHTTPRequestHandler(http.server.CGIHTTPRequestHandler):
    def do_GET(self):
        if self.path == '/upload': send_upload_page(self)
        else: http.server.CGIHTTPRequestHandler.do_GET(self)
    
    def do_POST(self):
        if self.path == '/upload':
            result = receive_upload(self)
            if result[0] < http.HTTPStatus.BAD_REQUEST:
                self.send_response(result[0], result[1])
                self.end_headers()
            else:
                self.send_error(result[0], result[1])
        else:
            http.server.CGIHTTPRequestHandler.do_POST(self)

def ssl_wrap(socket):
    server_root = pathlib.Path(args.directory).resolve()
    
    if server_root in pathlib.Path(args.server_certificate).resolve().parents:
        print('Server certificate \'{}\' is inside web server root \'{}\', exiting'.format(
            args.server_certificate, server_root))
        sys.exit(3)
    if args.client_certificate:
        if server_root in pathlib.Path(args.client_certificate).resolve().parents:
            print('Client certificate \'{}\' is inside web server root \'{}\', exiting'.format(
                args.client_certificate, server_root))
            sys.exit(3)
    
    try:
        context = ssl.create_default_context(ssl.Purpose.CLIENT_AUTH)
        context.load_cert_chain(certfile=args.server_certificate)
    except FileNotFoundError:
        print('Server certificate \'{}\' not found, exiting'.format(args.server_certificate))
        sys.exit(4)
    
    try:
        if args.client_certificate:
            context.load_verify_locations(cafile=args.client_certificate)
            context.verify_mode = ssl.CERT_REQUIRED
    except FileNotFoundError:
        print('Client certificate \'{}\' not found, exiting'.format(args.client_certificate))
        sys.exit(4)
    
    try:
        return context.wrap_socket(socket, server_side=True)
    except ssl.SSLError as e:
        print('SSL error: {}, exiting'.format(e))
        sys.exit(5)

if sys.version_info.major == 3 and sys.version_info.minor < 8:
    from http.server import BaseHTTPRequestHandler
    
    # The only difference in http.server.test() between Python 3.6 and 3.7 is the default value of ServerClass
    if sys.version_info.minor < 7: from http.server import HTTPServer as DefaultHTTPServer
    else: from http.server import ThreadingHTTPServer as DefaultHTTPServer
    
    # Copy of http.server.test() from Python 3.7. ssl_wrap() call added and print statement updaed for HTTPS
    def test(HandlerClass=BaseHTTPRequestHandler,
             ServerClass=DefaultHTTPServer,
             protocol="HTTP/1.0", port=8000, bind=""):
        """Test the HTTP request handler class.
        
        This runs an HTTP server on port 8000 (or the port argument).
        
        """
        server_address = (bind, port)
        
        HandlerClass.protocol_version = protocol
        with ServerClass(server_address, HandlerClass) as httpd:
            if args.server_certificate: httpd.socket = ssl_wrap(httpd.socket)
            
            sa = httpd.socket.getsockname()
            serve_message = "Serving {proto} on {host} port {port} ({proto_lower}://{host}:{port}/) ..."
            print(serve_message.format(host=sa[0], port=sa[1], proto=PROTOCOL, 
                proto_lower=PROTOCOL.lower()))
            try:
                httpd.serve_forever()
            except KeyboardInterrupt:
                print("\nKeyboard interrupt received, exiting.")
                sys.exit(0)
else:
    from http.server import BaseHTTPRequestHandler
    from http.server import ThreadingHTTPServer
    from http.server import _get_best_family
    
    # Copy of http.server.test() from Python 3.8. ssl_wrap() call added and print statement updaed for HTTPS
    def test(HandlerClass=BaseHTTPRequestHandler,
             ServerClass=ThreadingHTTPServer,
             protocol="HTTP/1.0", port=8000, bind=None):
        """Test the HTTP request handler class.
        
        This runs an HTTP server on port 8000 (or the port argument).
        
        """
        ServerClass.address_family, addr = _get_best_family(bind, port)
        
        HandlerClass.protocol_version = protocol
        with ServerClass(addr, HandlerClass) as httpd:
            if args.server_certificate: httpd.socket = ssl_wrap(httpd.socket)
            
            host, port = httpd.socket.getsockname()[:2]
            url_host = f'[{host}]' if ':' in host else host
            print(
                f"Serving {PROTOCOL} on {host} port {port} "
                f"({PROTOCOL.lower()}://{url_host}:{port}/) ..."
            )
            try:
                httpd.serve_forever()
            except KeyboardInterrupt:
                print("\nKeyboard interrupt received, exiting.")
                sys.exit(0)

def main():
    global args, PROTOCOL
    
    # In Python 3.8, http.server.test() was altered to use None instead of '' as the default for its bind parameter
    if sys.version_info.major == 3 and sys.version_info.minor < 8:
        bind_default = ''
    else:
        bind_default = None
    
    parser = argparse.ArgumentParser()
    parser.add_argument('port', type=int, default=8000, nargs='?',
        help='Specify alternate port [default: 8000]')
    parser.add_argument('--cgi', action='store_true',
        help='Run as CGI Server')
    parser.add_argument('--bind', '-b', default=bind_default, metavar='ADDRESS',
        help='Specify alternate bind address [default: all interfaces]')
    parser.add_argument('--token', '-t', type=str,
        help='Specify alternate token [default: \'\']')
    parser.add_argument('--server-certificate', '--certificate', '-c',
        help='Specify HTTPS server certificate to use [default: none]')
    parser.add_argument('--client-certificate',
        help='Specify HTTPS client certificate to accept for mutual TLS [default: none]')
    
    # Directory option was added to http.server in Python 3.7
    if sys.version_info.major > 3 or sys.version_info.minor >= 7:
        parser.add_argument('--directory', '-d', default=os.getcwd(),
            help='Specify alternative directory [default:current directory]')
    
    args = parser.parse_args()
    if not hasattr(args, 'directory'): args.directory = os.getcwd()
    PROTOCOL = 'HTTPS' if args.server_certificate else 'HTTP' # Just for log statements
    
    if args.cgi:
        handler_class = CGIHTTPRequestHandler
    elif sys.version_info.major == 3 and sys.version_info.minor < 7:
        handler_class = SimpleHTTPRequestHandler
    else:
        handler_class = functools.partial(SimpleHTTPRequestHandler, directory=args.directory)
    
    print('File upload available at /upload')
    
    # This was added to http.server's main section in Python 3.8
    if sys.version_info.major == 3 and sys.version_info.minor < 8:
        test(
            HandlerClass=handler_class,
            port=args.port,
            bind=args.bind,
        )
    else:
        class DualStackServer(http.server.ThreadingHTTPServer):
            def server_bind(self):
                # suppress exception when protocol is IPv4
                with contextlib.suppress(Exception):
                    self.socket.setsockopt(
                        socket.IPPROTO_IPV6, socket.IPV6_V6ONLY, 0)
                return super().server_bind()
        
        test(
            HandlerClass=handler_class,
            ServerClass=DualStackServer,
            port=args.port,
            bind=args.bind,
        )
