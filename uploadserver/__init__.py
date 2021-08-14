import http.server, http, cgi, pathlib, tempfile, shutil, os
from streaming_form_data import StreamingFormDataParser
from streaming_form_data.targets import FileTarget, SHA256Target
from tqdm import tqdm

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
    result = http.HTTPStatus.NO_CONTENT
    
    form = cgi.FieldStorage(fp=handler.rfile, headers=handler.headers, environ={'REQUEST_METHOD': 'POST'})
    if 'files' not in form:
        result = http.HTTPStatus.BAD_REQUEST
        return result
    fields = form['files']
    if not isinstance(fields, list): fields = [fields]
    
    for field in fields:
        if field.file and field.filename:
            filename = field.filename
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
            filepath = get_secure_path(filename)
            with open(filepath, 'wb') as f:
                f.write(field.file.read())
                handler.log_message('Upload of "{}" accepted'.format(filename))
    
    return result

def receive_streaming_upload(handler):
    result = http.HTTPStatus.INTERNAL_SERVER_ERROR

    if TOKEN:
        # server started with token.
        if 'token' not in handler.headers or handler.headers['token'] != TOKEN:
            # no token or token error
            handler.log_message('Upload rejected (bad token)')
            result = http.HTTPStatus.FORBIDDEN
            return result

    if 'filename' not in handler.headers or not handler.headers['filename']:
        handler.log_message('Upload rejected (no filename)')
        result = http.HTTPStatus.BAD_REQUEST
        return result

    file_name = handler.headers['filename']
    file_path = get_secure_path(file_name)

    if not file_path:
        result = http.HTTPStatus.BAD_REQUEST
        return result

    try:
        # Initialize temporary file
        temporary_file = tempfile.NamedTemporaryFile(delete=False)
        temporary_file_path = temporary_file.name

        # Initialize parser
        file_hash = SHA256Target()
        parser = StreamingFormDataParser(headers=handler.headers)
        parser.register('file', FileTarget(temporary_file_path))
        parser.register('file', file_hash)

        # Size of chunks to read from remote file
        current_chunk_size = 1024

        # Total length of remote file
        total_size = int(handler.headers['Content-Length'])
        current_size = 0

        # Process upload in chunks
        with tqdm(desc='Receiving ' + file_name, total=total_size, dynamic_ncols=True, mininterval=1, unit='B', unit_scale=True) as progress_bar:
            while current_size < total_size:
                current_size += current_chunk_size
                if current_size > total_size:
                    current_chunk_size += total_size - current_size
                progress_bar.update(current_chunk_size)
                chunk = handler.rfile.read(current_chunk_size)
                if chunk:
                    parser.data_received(chunk)
                else:
                    raise Exception('Transfer was interrupted')

        # Move temporary file to final destination
        shutil.move(temporary_file_path, file_path)
        handler.log_message('SHA-256 hashsum of {}: {}'.format(file_name, file_hash.value))
    except Exception as exception:
        handler.log_message(str(exception))

        # Delete temporary file if present
        if os.path.isfile(temporary_file_path):
            handler.log_message('Delete temporary file')
            os.remove(temporary_file_path)

    return http.HTTPStatus.NO_CONTENT

def get_secure_path(file):
    current_directory = pathlib.Path.cwd()
    path = pathlib.Path(current_directory).joinpath(file).resolve()

    if path.is_relative_to(current_directory):
        # File stays in current directory
        return path

    # Path traversal was attempted
    return None

class SimpleHTTPRequestHandler(http.server.SimpleHTTPRequestHandler):
    def do_GET(self):
        if self.path == '/upload': send_upload_page(self)
        else: http.server.SimpleHTTPRequestHandler.do_GET(self)
    
    def do_POST(self):
        if self.path == '/upload':
            if STREAMING:
                retcode = receive_streaming_upload(self)
            else:
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
