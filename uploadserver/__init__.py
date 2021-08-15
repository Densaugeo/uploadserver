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
    handler.send_header("Content-Type", 'text/html; charset=utf-8')
    handler.send_header("Content-Length", len(upload_page))
    handler.end_headers()
    handler.wfile.write(upload_page)

def receive_upload(handler):
    result = 0
    
    form = cgi.FieldStorage(fp=handler.rfile, headers=handler.headers, environ={'REQUEST_METHOD': 'POST'})
    if 'files' not in form: return
    fields = form['files']
    if not isinstance(fields, list): fields = [fields]
    
    for field in fields:
        if field.file and field.filename:
            filename = pathlib.Path(field.filename).name
        else:
            filename = None
    
        if TOKEN:
            # server started with token.
            if 'token' not in form or form['token'].value != TOKEN:
                # no token or token error
                handler.log_message('Upload of "{}" rejected (bad token)'.format(filename))
                result = http.HTTPStatus.FORBIDDEN
                continue # continue so if a multiple file upload is rejected, each file will be logged
        
        if filename:
            with open(pathlib.Path(DIRECTORY) / filename, 'wb') as f:
                f.write(field.file.read())
                handler.log_message('Upload of "{}" accepted'.format(filename))
    
    return result

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
            self.send_response(http.HTTPStatus.NO_CONTENT)
            self.end_headers()
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
            self.send_response(http.HTTPStatus.NO_CONTENT)
            self.end_headers()
        else: http.server.CGIHTTPRequestHandler.do_POST(self)
