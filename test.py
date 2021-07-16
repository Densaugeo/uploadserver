import os, requests, unittest, subprocess, time
from pathlib import Path

def setUpModule():
    os.mkdir(Path(__file__).parent / 'test-temp')
    os.chdir(Path(__file__).parent / 'test-temp')
    os.symlink('../uploadserver', 'uploadserver')

class Suite(unittest.TestCase):
    def setUp(self):
        print()
    
    def tearDown(self):
        self.server.terminate()
    
    # Verify a basic test can run. Most importantly, verify the sleep is long enough for the sever to start
    def test_basic(self):
        self.server = subprocess.Popen(['python3', '-u', '-m', 'uploadserver'])
        time.sleep(0.1)
        
        res = requests.get('http://127.0.0.1:8000/')
        self.assertEqual(res.status_code, 200)
    
    # Verify the --port argument is properly passed to the underlying http.server
    def test_argument_passthrough(self):
        self.server = subprocess.Popen(['python3', '-u', '-m', 'uploadserver', '8080'])
        time.sleep(0.1)
        
        res = requests.get('http://127.0.0.1:8080/')
        self.assertEqual(res.status_code, 200)
        self.assertRaises(requests.ConnectionError, lambda: requests.get('http://127.0.0.1:8000/'))
    
    # Verify /upload at least responds to GET
    def test_upload_page_exists(self):
        self.server = subprocess.Popen(['python3', '-u', '-m', 'uploadserver'])
        time.sleep(0.1)
        
        res = requests.get('http://127.0.0.1:8000/upload')
        self.assertEqual(res.status_code, 200)
    
    # Simple upload test
    def test_upload(self):
        self.server = subprocess.Popen(['python3', '-u', '-m', 'uploadserver'])
        time.sleep(0.1)
        
        res = requests.post('http://127.0.0.1:8000/upload', files={
            'file_1': ('a-file', 'file-content'),
        })
        self.assertEqual(res.status_code, 200)
        
        with open('a-file') as f: self.assertEqual(f.read(), 'file-content')
    
    # Verify uploads replace files of the same name
    def test_upload_same_name(self):
        self.server = subprocess.Popen(['python3', '-u', '-m', 'uploadserver'])
        time.sleep(0.1)
        
        res = requests.post('http://127.0.0.1:8000/upload', files={
            'file_1': ('a-file', 'file-content'),
        })
        self.assertEqual(res.status_code, 200)
        res = requests.post('http://127.0.0.1:8000/upload', files={
            'file_1': ('a-file', 'file-content-replaced'),
        })
        self.assertEqual(res.status_code, 200)
        
        with open('a-file') as f: self.assertEqual(f.read(), 'file-content-replaced')
    
    # Verify directory traversal attempts are contained within server folder
    def test_directory_traversal(self):
        self.server = subprocess.Popen(['python3', '-u', '-m', 'uploadserver'])
        time.sleep(0.1)
        
        res = requests.post('http://localhost:8000/upload', files={
            'file_1': ('../dt-name', 'dt-content'),
        })
        
        with open('dt-name') as f: self.assertEqual(f.read(), 'dt-content')
        self.assertFalse(Path('../dt-name').exists())
    
    # Verify uploads are accepted when the toekn option is used and the correct token is supplied
    def test_token_valid(self):
        self.server = subprocess.Popen(['python3', '-u', '-m', 'uploadserver', '-t', 'a-token'])
        time.sleep(0.1)
        
        # 'files' option is used for both files and other form data
        res = requests.post('http://localhost:8000/upload', files={
            'file_1': ('valid-token-upload', 'token-upload-content'),
            'token': (None, 'a-token'),
        })
        self.assertEqual(res.status_code, 200)
        
        with open('valid-token-upload') as f: self.assertEqual(f.read(), 'token-upload-content')
    
    # Verify uploads are rejected when the toekn option is used and an incorrect token is supplied
    def test_token_invalid(self):
        self.server = subprocess.Popen(['python3', '-u', '-m', 'uploadserver', '-t', 'a-token'])
        time.sleep(0.1)
        
        # 'files' option is used for both files and other form data
        res = requests.post('http://localhost:8000/upload', files={
            'file_1': ('invalid-token-upload', 'token-upload-content'),
            'token': (None, 'a-bad-token'),
        })
        self.assertEqual(res.status_code, 403)
        
        self.assertFalse(Path('invalid-token-upload').exists())
    
    # Verify uploads are rejected when the toekn option is used and no token is supplied
    def test_token_missing(self):
        self.server = subprocess.Popen(['python3', '-u', '-m', 'uploadserver', '-t', 'a-token'])
        time.sleep(0.1)
        
        # 'files' option is used for both files and other form data
        res = requests.post('http://localhost:8000/upload', files={
            'file_1': ('missing-token-upload', 'token-upload-content'),
        })
        self.assertEqual(res.status_code, 403)
        
        self.assertFalse(Path('missing-token-upload').exists())
    
    # Verify example curl command works
    def test_curl_example(self):
        self.server = subprocess.Popen(['python3', '-u', '-m', 'uploadserver'])
        time.sleep(0.1)
        
        subprocess.run(['curl', '-X', 'POST', 'http://localhost:8000/upload', '-F', 'file_1=@../LICENSE'])
        
        with open('LICENSE') as f_actual, open('../LICENSE') as f_expected:
                self.assertEqual(f_actual.read(), f_expected.read())
    
    # Verify example curl command with token works
    def test_curl_token_example(self):
        self.server = subprocess.Popen(['python3', '-u', '-m', 'uploadserver', '-t', 'helloworld'])
        time.sleep(0.1)
        
        subprocess.run(['curl', '-X', 'POST', 'http://localhost:8000/upload', '-F', 'file_1=@../README.md', '-F', 'token=helloworld'])
        
        with open('README.md') as f_actual, open('../README.md') as f_expected:
                self.assertEqual(f_actual.read(), f_expected.read())
