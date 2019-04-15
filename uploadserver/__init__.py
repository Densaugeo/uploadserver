import http.server, cgi, pathlib

upload_page = bytes('''<!DOCTYPE html>
<html><head><title>File Upload</title>
</head><body><h1>File Upload</h1>
<form action="upload" method="POST" enctype="multipart/form-data">
File name: <input name="file_1" type="file"><br>
<input type="submit">
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
    
    if 'file_1' in form and form['file_1'].file and form['file_1'].filename:
        with open(pathlib.Path.cwd() / pathlib.Path(form['file_1'].filename).name, 'wb') as f:
            f.write(form['file_1'].file.read())

class SimpleHTTPRequestHandler(http.server.SimpleHTTPRequestHandler):
    def do_GET(self):
        if self.path == '/upload': send_upload_page(self)
        else: http.server.SimpleHTTPRequestHandler.do_GET(self)
    
    def do_POST(self):
        if self.path == '/upload':
            receive_upload(self)
            send_upload_page(self)
        else: self.send_error(http.HTTPStatus.NOT_FOUND, "Can only POST to /upload")

class CGIHTTPRequestHandler(http.server.CGIHTTPRequestHandler):
    def do_GET(self):
        if self.path == '/upload': send_upload_page(self)
        else: http.server.CGIHTTPRequestHandler.do_GET(self)
    
    def do_POST(self):
        if self.path == '/upload':
            receive_upload(self)
            send_upload_page(self)
        else: http.server.CGIHTTPRequestHandler.do_POST(self)
