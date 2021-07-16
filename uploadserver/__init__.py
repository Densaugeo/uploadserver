import http.server, http, cgi, pathlib


TOKEN = ''
upload_page = bytes('''<!DOCTYPE html>
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
<input name="file_1" type="file" />
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
    handler.send_header("Content-Type", 'text/html; charset=utf-8')
    handler.send_header("Content-Length", len(upload_page))
    handler.end_headers()
    handler.wfile.write(upload_page)

def receive_upload(handler):
    form = cgi.FieldStorage(fp=handler.rfile, headers=handler.headers, environ={'REQUEST_METHOD': 'POST'})
    if TOKEN:
        # server started with token.
        if 'token' not in form or form['token'].value != TOKEN:
            # no token or token error
            return http.HTTPStatus.FORBIDDEN
    if 'file_1' in form and form['file_1'].file and form['file_1'].filename:
        with open(pathlib.Path.cwd() / pathlib.Path(form['file_1'].filename).name, 'wb') as f:
            f.write(form['file_1'].file.read())
            return 0

class SimpleHTTPRequestHandler(http.server.SimpleHTTPRequestHandler):
    def do_GET(self):
        if self.path == '/upload': send_upload_page(self)
        else: http.server.SimpleHTTPRequestHandler.do_GET(self)
    
    def do_POST(self):
        if self.path == '/upload':
            retcode = receive_upload(self)
            if http.HTTPStatus.FORBIDDEN == retcode:
                self.send_error(retcode, "Token is enabled on this server, and your token is error")
                return
            send_upload_page(self)
        else: self.send_error(http.HTTPStatus.NOT_FOUND, "Can only POST to /upload")

class CGIHTTPRequestHandler(http.server.CGIHTTPRequestHandler):
    def do_GET(self):
        if self.path == '/upload': send_upload_page(self)
        else: http.server.CGIHTTPRequestHandler.do_GET(self)
    
    def do_POST(self):
        if self.path == '/upload':
            retcode = receive_upload(self)
            if http.HTTPStatus.FORBIDDEN == retcode:
                self.send_error(retcode, "Token is enabled on this server, and your token is error")
                return
            send_upload_page(self)
        else: http.server.CGIHTTPRequestHandler.do_POST(self)
