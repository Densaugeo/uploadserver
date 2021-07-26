import os, requests, unittest, subprocess, time, urllib3, socket, shutil
from pathlib import Path

assert 'VERBOSE' in os.environ, '$VERBOSE envionment variable not set'
VERBOSE = os.environ['VERBOSE']
assert VERBOSE in ['0', '1'], '$VERBOSE must be 0 or 1'
VERBOSE = int(VERBOSE)

assert 'PROTOCOL' in os.environ, '$PROTOCOL envionment variable not set'
PROTOCOL = os.environ['PROTOCOL']
assert PROTOCOL in ['HTTP', 'HTTPS'], 'Unknown $PROTOCOL: {}'.format(PROTOCOL)

def setUpModule():
    os.mkdir(Path(__file__).parent / 'test-temp')
    os.chdir(Path(__file__).parent / 'test-temp')
    os.symlink('../uploadserver', 'uploadserver')

class Suite(unittest.TestCase):
    def setUp(self):
        print()
        urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)
    
    def tearDown(self):
        if hasattr(self, 'server'): self.server.terminate()
    
    # Verify a basic test can run. Most importantly, verify the sleep is long enough for the sever to start
    def test_basic(self):
        self.spawn_server()
        
        res = self.get('/')
        self.assertEqual(res.status_code, 200)
    
    # Verify the --port argument is properly passed to the underlying http.server
    def test_argument_passthrough(self):
        self.spawn_server(port=8080)
        
        res = self.get('/', port=8080)
        self.assertEqual(res.status_code, 200)
        self.assertRaises(requests.ConnectionError, lambda: self.get('/'))
    
    # Verify /upload at least responds to GET
    def test_upload_page_exists(self):
        self.spawn_server()
        
        res = self.get('/upload')
        self.assertEqual(res.status_code, 200)
    
    # Simple upload test
    def test_upload(self):
        self.spawn_server()
        
        res = self.post('/upload', files={
            'files': ('a-file', 'file-content'),
        })
        self.assertEqual(res.status_code, 204)
        
        with open('a-file') as f: self.assertEqual(f.read(), 'file-content')
    
    # Verify uploads replace files of the same name
    def test_upload_same_name(self):
        self.spawn_server()
        
        res = self.post('/upload', files={
            'files': ('a-file', 'file-content'),
        })
        self.assertEqual(res.status_code, 204)
        res = self.post('/upload', files={
            'files': ('a-file', 'file-content-replaced'),
        })
        self.assertEqual(res.status_code, 204)
        
        with open('a-file') as f: self.assertEqual(f.read(), 'file-content-replaced')
    
    # Test a malformed upload
    def test_upload_bad_field_name(self):
        self.spawn_server()
        
        res = self.post('/upload', files={
            'file_foo': ('a-file', 'file-content'),
        })
        self.assertEqual(res.status_code, 204)
    
    # Verify multiple file upload works
    def test_multiple_upload(self):
        self.spawn_server()
        
        res = self.post('/upload', files=[
            ('files', ('file-1', 'file-content-1')),
            ('files', ('file-2', 'file-content-2')),
        ])
        self.assertEqual(res.status_code, 204)
        
        with open('file-1') as f: self.assertEqual(f.read(), 'file-content-1')
        with open('file-2') as f: self.assertEqual(f.read(), 'file-content-2')
    
    # Verify directory traversal attempts are contained within server folder
    def test_directory_traversal(self):
        self.spawn_server()
        
        res = self.post('/upload', files={
            'files': ('../dt-name', 'dt-content'),
        })
        
        with open('dt-name') as f: self.assertEqual(f.read(), 'dt-content')
        self.assertFalse(Path('../dt-name').exists())
    
    # Verify uploads are accepted when the toekn option is used and the correct token is supplied
    def test_token_valid(self):
        self.spawn_server(token='a-token')
        
        # 'files' option is used for both files and other form data
        res = self.post('/upload', files={
            'files': ('valid-token-upload', 'token-upload-content'),
            'token': (None, 'a-token'),
        })
        self.assertEqual(res.status_code, 204)
        
        with open('valid-token-upload') as f: self.assertEqual(f.read(), 'token-upload-content')
    
    # Verify uploads are rejected when the toekn option is used and an incorrect token is supplied
    def test_token_invalid(self):
        self.spawn_server(token='a-token')
        
        # 'files' option is used for both files and other form data
        res = self.post('/upload', files={
            'files': ('invalid-token-upload', 'token-upload-content'),
            'token': (None, 'a-bad-token'),
        })
        self.assertEqual(res.status_code, 403)
        
        self.assertFalse(Path('invalid-token-upload').exists())
    
    # Verify uploads are rejected when the toekn option is used and no token is supplied
    def test_token_missing(self):
        self.spawn_server(token='a-token')
        
        # 'files' option is used for both files and other form data
        res = self.post('/upload', files={
            'files': ('missing-token-upload', 'token-upload-content'),
        })
        self.assertEqual(res.status_code, 403)
        
        self.assertFalse(Path('missing-token-upload').exists())
    
    if PROTOCOL == 'HTTPS':
        # Verify that uploadserver will refuse to start if given a certificate inside its server root
        def test_certificate_not_allowed_in_root(self):
            shutil.copyfile('../localhost.pem', 'localhost.pem')
            
            result = subprocess.run(
                ['python', '-m', 'uploadserver', '-c', 'localhost.pem'],
                stdout=None if VERBOSE else subprocess.DEVNULL,
                stderr=None if VERBOSE else subprocess.DEVNULL,
            )
            
            self.assertEqual(result.returncode, 3)
    
    # Verify example curl command works
    def test_curl_example(self):
        self.spawn_server()
        
        result = subprocess.run([
                'curl', '-X', 'POST', '{}://localhost:8000/upload'.format(PROTOCOL.lower()),
                '-k', '-F', 'files=@../test-files/simple-example.txt',
            ],
            stdout=None if VERBOSE else subprocess.DEVNULL,
            stderr=None if VERBOSE else subprocess.DEVNULL,
        )
        
        self.assertEqual(result.returncode, 0)
        
        with open('simple-example.txt') as f_actual, open('../test-files/simple-example.txt') as f_expected:
                self.assertEqual(f_actual.read(), f_expected.read())
    
    # Verify example curl command with multiple files works
    def test_curl_multiple_example(self):
        self.spawn_server()
        
        result = subprocess.run([
                'curl', '-X', 'POST', '{}://localhost:8000/upload'.format(PROTOCOL.lower()),
                '-k', '-F', 'files=@../test-files/multiple-example-1.txt',
                '-F', 'files=@../test-files/multiple-example-2.txt',
            ],
            stdout=None if VERBOSE else subprocess.DEVNULL,
            stderr=None if VERBOSE else subprocess.DEVNULL,
        )
        
        self.assertEqual(result.returncode, 0)
        
        with open('multiple-example-1.txt') as f_actual, open('../test-files/multiple-example-1.txt') as f_expected:
                self.assertEqual(f_actual.read(), f_expected.read())
        with open('multiple-example-2.txt') as f_actual, open('../test-files/multiple-example-2.txt') as f_expected:
                self.assertEqual(f_actual.read(), f_expected.read())
    
    # Verify example curl command with token works
    def test_curl_token_example(self):
        self.spawn_server(token='helloworld')
        
        result = subprocess.run([
                'curl', '-X', 'POST', '{}://localhost:8000/upload'.format(PROTOCOL.lower()),
                '-k', '-F', 'files=@../test-files/token-example.txt', '-F', 'token=helloworld',
            ],
            stdout=None if VERBOSE else subprocess.DEVNULL,
            stderr=None if VERBOSE else subprocess.DEVNULL,
        )
        self.assertEqual(result.returncode, 0)
        
        with open('token-example.txt') as f_actual, open('../test-files/token-example.txt') as f_expected:
                self.assertEqual(f_actual.read(), f_expected.read())
    
    def spawn_server(self, port=None, token=None,
        certificate=('../localhost.pem' if PROTOCOL == 'HTTPS' else None)
    ):
        args = ['python3', '-u', '-m', 'uploadserver']
        if port: args += [str(port)]
        if token: args += ['-t', token]
        if certificate: args += ['-c', certificate]
        
        self.server = subprocess.Popen(
            args,
            stdout=None if VERBOSE else subprocess.DEVNULL,
            stderr=None if VERBOSE else subprocess.DEVNULL,
        )
        
        # Wait for server to finish starting
        s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        for _ in range(10):
            try:
                time.sleep(0.1)
                s.connect(('localhost', port or 8000))
                s.close()
                break
            except ConnectionRefusedError:
                pass
        else:
            raise Exception('Port {} not responding. Did the server fail to start?'.format(port or 8000))
    
    def get(self, path, port=8000, *args, **kwargs):
        return requests.get('{}://127.0.0.1:{}{}'.format(PROTOCOL.lower(), port, path), verify=False, *args, **kwargs)
    
    def post(self, path, port=8000, *args, **kwargs):
        return requests.post('{}://127.0.0.1:{}{}'.format(PROTOCOL.lower(), port, path), verify=False, *args, **kwargs)
