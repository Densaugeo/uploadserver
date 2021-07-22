import os, requests, unittest, subprocess, time, urllib3
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
        self.server.terminate()
    
    # Verify a basic test can run. Most importantly, verify the sleep is long enough for the sever to start
    def test_basic(self):
        self.spawn_server()
        
        res = self.get('/')
        self.assertEqual(res.status_code, 200)
    
    # Verify the --port argument is properly passed to the underlying http.server
    def test_argument_passthrough(self):
        self.spawn_server(['8080'])
        
        res = self.get('/', port=8080)
        self.assertEqual(res.status_code, 200)
        self.assertRaises(requests.ConnectionError, lambda: self.get('/', retries=0))
    
    # Verify /upload at least responds to GET
    def test_upload_page_exists(self):
        self.spawn_server()
        
        res = self.get('/upload')
        self.assertEqual(res.status_code, 200)
    
    # Simple upload test
    def test_upload(self):
        self.spawn_server()
        
        res = self.post('/upload', files={
            'file_1': ('a-file', 'file-content'),
        })
        self.assertEqual(res.status_code, 200)
        
        with open('a-file') as f: self.assertEqual(f.read(), 'file-content')
    
    # Verify uploads replace files of the same name
    def test_upload_same_name(self):
        self.spawn_server()
        
        res = self.post('/upload', files={
            'file_1': ('a-file', 'file-content'),
        })
        self.assertEqual(res.status_code, 200)
        res = self.post('/upload', files={
            'file_1': ('a-file', 'file-content-replaced'),
        })
        self.assertEqual(res.status_code, 200)
        
        with open('a-file') as f: self.assertEqual(f.read(), 'file-content-replaced')
    
    # Test a malformed upload
    def test_upload_bad_field_name(self):
        self.spawn_server()
        
        res = self.post('/upload', files={
            'file_foo': ('a-file', 'file-content'),
        })
        self.assertEqual(res.status_code, 200)
    
    # Verify directory traversal attempts are contained within server folder
    def test_directory_traversal(self):
        self.spawn_server()
        
        res = self.post('/upload', files={
            'file_1': ('../dt-name', 'dt-content'),
        })
        
        with open('dt-name') as f: self.assertEqual(f.read(), 'dt-content')
        self.assertFalse(Path('../dt-name').exists())
    
    # Verify uploads are accepted when the toekn option is used and the correct token is supplied
    def test_token_valid(self):
        self.spawn_server(['-t', 'a-token'])
        
        # 'files' option is used for both files and other form data
        res = self.post('/upload', files={
            'file_1': ('valid-token-upload', 'token-upload-content'),
            'token': (None, 'a-token'),
        })
        self.assertEqual(res.status_code, 200)
        
        with open('valid-token-upload') as f: self.assertEqual(f.read(), 'token-upload-content')
    
    # Verify uploads are rejected when the toekn option is used and an incorrect token is supplied
    def test_token_invalid(self):
        self.spawn_server(['-t', 'a-token'])
        
        # 'files' option is used for both files and other form data
        res = self.post('/upload', files={
            'file_1': ('invalid-token-upload', 'token-upload-content'),
            'token': (None, 'a-bad-token'),
        })
        self.assertEqual(res.status_code, 403)
        
        self.assertFalse(Path('invalid-token-upload').exists())
    
    # Verify uploads are rejected when the toekn option is used and no token is supplied
    def test_token_missing(self):
        self.spawn_server(['-t', 'a-token'])
        
        # 'files' option is used for both files and other form data
        res = self.post('/upload', files={
            'file_1': ('missing-token-upload', 'token-upload-content'),
        })
        self.assertEqual(res.status_code, 403)
        
        self.assertFalse(Path('missing-token-upload').exists())
    
    # Verify example curl command works
    def test_curl_example(self):
        self.spawn_server()
        
        time.sleep(0.2)
        result = subprocess.run(
            ['curl', '-X', 'POST', '{}://localhost:8000/upload'.format(PROTOCOL.lower()), '-k', '-F', 'file_1=@../LICENSE'],
            stdout=None if VERBOSE else subprocess.DEVNULL,
            stderr=None if VERBOSE else subprocess.DEVNULL,
        )
        
        self.assertEqual(result.returncode, 0)
        
        with open('LICENSE') as f_actual, open('../LICENSE') as f_expected:
                self.assertEqual(f_actual.read(), f_expected.read())
    
    # Verify example curl command with token works
    def test_curl_token_example(self):
        self.spawn_server(['-t', 'helloworld'])
        
        time.sleep(0.2)
        result = subprocess.run(
            ['curl', '-X', 'POST', '{}://localhost:8000/upload'.format(PROTOCOL.lower()), '-k', '-F', 'file_1=@../README.md', '-F', 'token=helloworld'],
            stdout=None if VERBOSE else subprocess.DEVNULL,
            stderr=None if VERBOSE else subprocess.DEVNULL,
        )
        self.assertEqual(result.returncode, 0)
        
        with open('README.md') as f_actual, open('../README.md') as f_expected:
                self.assertEqual(f_actual.read(), f_expected.read())
    
    def spawn_server(self, args=[]):
        args = ['python3', '-u', '-m', 'uploadserver'] + args
        if PROTOCOL == 'HTTPS': args += ['-c', '../localhost.pem']
        self.server = subprocess.Popen(
            args,
            stdout=None if VERBOSE else subprocess.DEVNULL,
            stderr=None if VERBOSE else subprocess.DEVNULL,
        )
    
    def get(self, path, port=8000, retries=10, *args, **kwargs):
        for i in range(retries + 1):
            try:
                return requests.get('{}://127.0.0.1:{}{}'.format(PROTOCOL.lower(), port, path), verify=False, *args, **kwargs)
            except Exception as e:
                if i == retries: raise e
            
            time.sleep(0.1)
    
    def post(self, path, port=8000, retries=10, *args, **kwargs):
        for i in range(retries + 1):
            try:
                return requests.post('{}://127.0.0.1:{}{}'.format(PROTOCOL.lower(), port, path), verify=False, *args, **kwargs)
            except Exception as e:
                if i == retries: raise e
            
            time.sleep(0.1)
