import http.server, sys, argparse, uploadserver

if sys.version_info.major >= 3 and sys.version_info.minor >= 7:
    import os, functools

if sys.version_info.major >= 3 and sys.version_info.minor >= 8:
    import contextlib

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
        http.server.test(
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
        
        http.server.test(
            HandlerClass=handler_class,
            ServerClass=DualStackServer,
            port=args.port,
            bind=args.bind,
        )
