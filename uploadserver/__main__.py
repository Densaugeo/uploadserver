import http.server, argparse, uploadserver

if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--cgi', action='store_true',
                       help='Run as CGI Server')
    parser.add_argument('--bind', '-b', default='', metavar='ADDRESS',
                        help='Specify alternate bind address '
                             '[default: all interfaces]')
    parser.add_argument('port', action='store',
                        default=8000, type=int,
                        nargs='?',
                        help='Specify alternate port [default: 8000]')
    args = parser.parse_args()
    if args.cgi:
        handler_class = uploadserver.CGIHTTPRequestHandler
    else:
        handler_class = uploadserver.SimpleHTTPRequestHandler
    print('File upload available at /upload')
    http.server.test(HandlerClass=handler_class, port=args.port, bind=args.bind)
