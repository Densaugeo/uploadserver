import http.server, sys, argparse, uploadserver, ssl, pathlib

if sys.version_info.major >= 3 and sys.version_info.minor >= 7:
    import os, functools

if sys.version_info.major >= 3 and sys.version_info.minor >= 8:
    import contextlib

def ssl_wrap(socket):
    try:
        return ssl.wrap_socket(socket, certfile=args.certificate, server_side=True)
    except FileNotFoundError:
        print('Certificate file \'{}\' not found'.format(args.certificate))
        sys.exit(1)
    except ssl.SSLError as e:
        print('SSL error loading certificate file \'{}\': {}'.format(args.certificate, e))
        sys.exit(1)

if sys.version_info.major == 3 and 6 <= sys.version_info.minor <= 7:
    from http.server import BaseHTTPRequestHandler
    
    # The only difference in http.server.test() between Python 3.6 and 3.7 is the default value of ServerClass
    if sys.version_info.minor == 6: from http.server import HTTPServer as DefaultHTTPServer
    else: from http.server import ThreadingHTTPServer as DefaultHTTPServer
    
    # Copy of http.server.test() from Python 3.7. ssl_wrap() call added
    def test(HandlerClass=BaseHTTPRequestHandler,
             ServerClass=DefaultHTTPServer,
             protocol="HTTP/1.0", port=8000, bind=""):
        """Test the HTTP request handler class.
        
        This runs an HTTP server on port 8000 (or the port argument).
        
        """
        server_address = (bind, port)
        
        HandlerClass.protocol_version = protocol
        with ServerClass(server_address, HandlerClass) as httpd:
            if args.certificate: httpd.socket = ssl_wrap(httpd.socket)
            
            sa = httpd.socket.getsockname()
            serve_message = "Serving HTTP on {host} port {port} (http://{host}:{port}/) ..."
            print(serve_message.format(host=sa[0], port=sa[1]))
            try:
                httpd.serve_forever()
            except KeyboardInterrupt:
                print("\nKeyboard interrupt received, exiting.")
                sys.exit(0)
else:
    from http.server import BaseHTTPRequestHandler
    from http.server import ThreadingHTTPServer
    from http.server import _get_best_family
    
    # Copy of http.server.test() from Python 3.8. ssl_wrap() call added
    def test(HandlerClass=BaseHTTPRequestHandler,
             ServerClass=ThreadingHTTPServer,
             protocol="HTTP/1.0", port=8000, bind=None):
        """Test the HTTP request handler class.
        
        This runs an HTTP server on port 8000 (or the port argument).
        
        """
        ServerClass.address_family, addr = _get_best_family(bind, port)
        
        HandlerClass.protocol_version = protocol
        with ServerClass(addr, HandlerClass) as httpd:
            if args.certificate: httpd.socket = ssl_wrap(httpd.socket)
            
            host, port = httpd.socket.getsockname()[:2]
            url_host = f'[{host}]' if ':' in host else host
            print(
                f"Serving HTTP on {host} port {port} "
                f"(http://{url_host}:{port}/) ..."
            )
            try:
                httpd.serve_forever()
            except KeyboardInterrupt:
                print("\nKeyboard interrupt received, exiting.")
                sys.exit(0)

if __name__ == '__main__':
    # In Python 3.8, http.server.test() was altered to use None instead of '' as the default for its bind parameter
    if sys.version_info.major <= 3 and sys.version_info.minor < 8:
        bind_default = ''
    else:
        bind_default = None
    
    parser = argparse.ArgumentParser()
    parser.add_argument('--cgi', action='store_true', help='Run as CGI Server')
    parser.add_argument('--bind', '-b', default=bind_default, metavar='ADDRESS',
        help='Specify alternate bind address [default: all interfaces]')
    parser.add_argument('port', action='store', default=8000, type=int, nargs='?',
        help='Specify alternate port [default: 8000]')
    parser.add_argument('--token', '-t', action='store', default='', type=str, nargs='?',
        help='Specify alternate token [default: \'\']')
    parser.add_argument('--certificate', '-c', action='store', default=None, type=pathlib.Path,
        help='Specify certificate to use HTTPS [default: none]')

    # Directory option was added to http.server in Python 3.7
    if sys.version_info.major >= 3 and sys.version_info.minor >= 7:
        parser.add_argument('--directory', '-d', default=os.getcwd(),
            help='Specify alternative directory [default:current directory]')
    args = parser.parse_args()
    
    uploadserver.TOKEN = args.token
    if args.cgi:
        handler_class = uploadserver.CGIHTTPRequestHandler
    elif sys.version_info.major >= 3 and sys.version_info.minor >= 7:
        handler_class = functools.partial(uploadserver.SimpleHTTPRequestHandler, directory=args.directory)
    else:
        handler_class = uploadserver.SimpleHTTPRequestHandler
    
    print('File upload available at /upload')
    
    # This was added to http.server's main section in Python 3.8
    if sys.version_info.major <= 3 and sys.version_info.minor < 8:
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
