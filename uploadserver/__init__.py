import http.server, http, cgi, pathlib, tempfile, shutil, os
from streaming_form_data import StreamingFormDataParser
from streaming_form_data.targets import DirectoryTarget, ValueTarget

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
    with tempfile.TemporaryDirectory() as temporary_directory:

        # Initialize parser and targets
        parser = StreamingFormDataParser(headers=handler.headers)
        directory_target = DirectoryTarget(temporary_directory)
        token_target = ValueTarget()
        parser.register('files', directory_target)
        parser.register('token', token_target)

        # Size of chunks to read from remote
        current_chunk_size = 1024

        # Total length of remote file
        total_size = int(handler.headers['Content-Length'])
        current_size = 0

        # Process upload in chunks
        while current_size < total_size:
            current_size += current_chunk_size
            if current_size > total_size:
                current_chunk_size += total_size - current_size
            chunk = handler.rfile.read(current_chunk_size)
            if chunk:
                parser.data_received(chunk)
            else:
                handler.log_message('Transfer was interrupted')
                return http.HTTPStatus.BAD_REQUEST

        if TOKEN:
            # server started with token.
            if token_target.value.decode("utf-8") != TOKEN:
                # no token or token error
                handler.log_message('Upload rejected (bad token)')
                return http.HTTPStatus.FORBIDDEN

        # Move temporary files to final destination
        source_directory_path = pathlib.Path(temporary_directory)
        destination_directory_path = pathlib.Path.cwd()
        for multipart_filename in directory_target.multipart_filenames:
            shutil.move(source_directory_path / multipart_filename, destination_directory_path / multipart_filename)

    return http.HTTPStatus.NO_CONTENT

class SimpleHTTPRequestHandler(http.server.SimpleHTTPRequestHandler):
    def do_GET(self):
        if self.path == '/upload': send_upload_page(self)
        else: http.server.SimpleHTTPRequestHandler.do_GET(self)
    
    def do_POST(self):
        if self.path == '/upload':
            retcode = receive_upload(self)

            if http.HTTPStatus.BAD_REQUEST == retcode:
                self.send_error(retcode, 'Check your input parameters')
                return
            if http.HTTPStatus.FORBIDDEN == retcode:
                self.send_error(retcode, 'Token is enabled on this server, and your token is wrong')
                return
            if http.HTTPStatus.INTERNAL_SERVER_ERROR == retcode:
                self.send_error(retcode, 'Server error')
                return
            self.send_response(retcode)
            self.end_headers()
        else: self.send_error(http.HTTPStatus.NOT_FOUND, 'Can only POST to /upload')

class CGIHTTPRequestHandler(http.server.CGIHTTPRequestHandler):
    def do_GET(self):
        if self.path == '/upload': send_upload_page(self)
        else: http.server.CGIHTTPRequestHandler.do_GET(self)
    
    def do_POST(self):
        if self.path == '/upload':
            retcode = receive_upload(self)
            if http.HTTPStatus.FORBIDDEN == retcode:
                self.send_error(retcode, 'Token is enabled on this server, and your token is wrong')
                return
            self.send_response(http.HTTPStatus.NO_CONTENT)
            self.end_headers()
        else: http.server.CGIHTTPRequestHandler.do_POST(self)
