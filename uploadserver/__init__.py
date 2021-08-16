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
    handler.send_header('Content-Type', 'text/html; charset=utf-8')
    handler.send_header('Content-Length', len(upload_page))
    handler.end_headers()
    handler.wfile.write(upload_page)

def receive_upload(handler):
    result = (http.HTTPStatus.INTERNAL_SERVER_ERROR, 'Server error')
    
    upload_directory = pathlib.Path(DIRECTORY)
    
    form = cgi.FieldStorage(fp=handler.rfile, headers=handler.headers, environ={'REQUEST_METHOD': 'POST'})
    if 'files' not in form:
        return (http.HTTPStatus.BAD_REQUEST, 'Field "files" not found')
    
    fields = form['files']
    if not isinstance(fields, list):
    	fields = [fields]
    
    for field in fields:
        if field.file and field.filename:
            file_path = upload_directory / field.filename
        else:
            return (http.HTTPStatus.BAD_REQUEST, 'Field "filename" not found')
        
        if not file_path.resolve().is_relative_to(upload_directory):
            handler.log_message('Path traversal attempt: {}'.format(field.filename))
            return (http.HTTPStatus.BAD_REQUEST, 'Path traversal attempt')
        
        if TOKEN:
            # server started with token.
            if 'token' not in form or form['token'].value != TOKEN:
                # no token or token error
                handler.log_message('Upload of "{}" rejected (bad token)'.format(file_path.name))
                result = (http.HTTPStatus.FORBIDDEN, 'Token is enabled on this server, and your token is wrong')
                continue # continue so if a multiple file upload is rejected, each file will be logged
        
        with open(file_path, 'wb') as f:
            f.write(field.file.read())
            handler.log_message('Upload of "{}" accepted'.format(file_path.name))
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
          self.send_error(http.HTTPStatus.BAD_REQUEST, 'Can only POST to /upload')

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
          self.send_error(http.HTTPStatus.BAD_REQUEST, 'Can only POST to /upload') # TODO: Check if it corresponds to the previous implementation
