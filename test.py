import os, requests, unittest, subprocess, time, urllib3, socket, shutil, sys
from requests.auth import HTTPBasicAuth
from pathlib import Path

assert 'VERBOSE' in os.environ, '$VERBOSE envionment variable not set'
VERBOSE = os.environ['VERBOSE']
assert VERBOSE in ['0', '1'], '$VERBOSE must be 0 or 1'
VERBOSE = int(VERBOSE)

assert 'PROTOCOL' in os.environ, '$PROTOCOL envionment variable not set'
PROTOCOL = os.environ['PROTOCOL']
assert PROTOCOL in ['HTTP', 'HTTPS'], 'Unknown $PROTOCOL: {}'.format(PROTOCOL)

TEST_BASIC_AUTH = HTTPBasicAuth('foo', 'bar')
TEST_BASIC_AUTH_BAD_USER = HTTPBasicAuth('foo2', 'bar')
TEST_BASIC_AUTH_BAD_PASS = HTTPBasicAuth('foo', 'bar2')

def setUpModule():
    os.mkdir(Path(__file__).parent / 'test-temp')
    os.chdir(Path(__file__).parent / 'test-temp')
    os.symlink('../uploadserver', 'uploadserver')
    os.mkdir('directory-option-test')

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

    # Basic auth on everything
    def test_basic_auth(self):
        self.spawn_server(basic_auth=TEST_BASIC_AUTH)
        
        # auth GET / - succeeds
        res = self.get('/', auth=TEST_BASIC_AUTH)
        self.assertEqual(res.status_code, 200)
    
        # unauth GET / - fails
        res = self.get('/')
        self.assertEqual(res.status_code, 401)
    
        # baduser auth GET / - fails
        res = self.get('/', auth=TEST_BASIC_AUTH_BAD_USER)
        self.assertEqual(res.status_code, 401)
    
        # badpass auth GET / - fails
        res = self.get('/', auth=TEST_BASIC_AUTH_BAD_PASS)
        self.assertEqual(res.status_code, 401)
    
        self._test_basic_auth_upload()

    # Basic auth on upload only
    def test_basic_auth_upload(self):
        self.spawn_server(basic_auth_upload=TEST_BASIC_AUTH)
        
        # unauth GET / - succeeds
        res = self.get('/')
        self.assertEqual(res.status_code, 200)

        self._test_basic_auth_upload()
    
    def _test_basic_auth_upload(self):
        # auth POST /upload - succeeds
        res = self.post('/upload', auth=TEST_BASIC_AUTH, files={
            'files': ('a-file', 'file-content'),
        })
        self.assertEqual(res.status_code, 204)
        with open('a-file') as f: self.assertEqual(f.read(), 'file-content')

        # unauth POST /upload - fails
        res = self.post('/upload', files={
            'files': ('a-file', 'file-content'),
        })
        self.assertEqual(res.status_code, 401)

        # baduser POST /upload - fails
        res = self.post('/upload', auth=TEST_BASIC_AUTH_BAD_USER, files={
            'files': ('a-file', 'file-content'),
        })
        self.assertEqual(res.status_code, 401)

        # badpass POST /upload - fails
        res = self.post('/upload', auth=TEST_BASIC_AUTH_BAD_PASS, files={
            'files': ('a-file', 'file-content'),
        })
        self.assertEqual(res.status_code, 401)

    # Verify uploaded file is renamed if there is a collision
    def test_upload_same_name_default(self):
        file_name = 'b-file'
        file_renamed = f'{file_name} (1)'  # this is the auto-renaming pattern
        
        self.spawn_server()
        
        res = self.post('/upload', files={
            'files': (file_name, 'file-content'),
        })
        self.assertEqual(res.status_code, 204)
        res = self.post('/upload', files={
            'files': (file_name, 'file-content-same-name'),
        })
        self.assertEqual(res.status_code, 204)
        
        with open(file_name) as f: self.assertEqual(f.read(), 'file-content')
        with open(file_renamed) as f: self.assertEqual(f.read(), 'file-content-same-name')
        
    # Verify uploads replace existing file with the same name
    def test_upload_same_name_replace(self):
        file_name = 'c-file'
        file_renamed = f'{file_name} (1)'  # this is the auto-renaming pattern
        
        self.spawn_server(allow_replace=True)
        
        res = self.post('/upload', files={
            'files': (file_name, 'file-content'),
        })
        self.assertEqual(res.status_code, 204)
        res = self.post('/upload', files={
            'files': (file_name, 'file-content-replaced'),
        })
        self.assertEqual(res.status_code, 204)
        
        with open(file_name) as f: self.assertEqual(f.read(), 'file-content-replaced')
        self.assertEqual(os.path.isfile(file_renamed), False)
    
    def test_upload_bad_path(self):
        self.spawn_server()
        
        res = self.post('/uploadx', files={
            'file_foo': ('a-file', 'file-content'),
        })
        self.assertEqual(res.status_code, 404)
    
    # Test a malformed upload
    def test_upload_bad_field_name(self):
        self.spawn_server()
        
        res = self.post('/upload', files={
            'file_foo': ('a-file', 'file-content'),
        })
        self.assertEqual(res.status_code, 400)
    
    def test_upload_no_files(self):
        self.spawn_server()
        
        res = self.post('/upload', files={
            'files': ('', ''),
        })
        self.assertEqual(res.status_code, 400)
    
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
    
    # Uploads large enough to need a temp file have slightly different handling that needs to be tested
    def test_large_upload(self):
        self.spawn_server()
        
        file_content = 1024*'a' + 1024*'b' + 1024*'c' + 1024*'d'
        
        res = self.post('/upload', files={
            'files': ('a-larger-file', file_content),
        })
        self.assertEqual(res.status_code, 204)
        
        with open('a-larger-file') as f: self.assertEqual(f.read(), file_content)
    
    # Verify directory traversal attempts are contained within server folder
    def test_directory_traversal(self):
        self.spawn_server()
        
        res = self.post('/upload', files={
            'files': ('../dt-name', 'dt-content'),
        })
        
        with open('dt-name') as f: self.assertEqual(f.read(), 'dt-content')
        self.assertFalse(Path('../dt-name').exists())
    
    # Directory option was added to http.server in Python 3.7
    if sys.version_info.major >= 3 and sys.version_info.minor >= 7:
        def test_upload_respects_directory(self):
            self.spawn_server(directory='directory-option-test')
            
            res = self.post('/upload', files={
                'files': ('directory-file', 'file-content'),
            })
            self.assertEqual(res.status_code, 204)
            
            with open('directory-option-test/directory-file') as f: self.assertEqual(f.read(), 'file-content')
    
    # There's no client-side testing to verify the theme or UI, but I can at least make sure the server runs
    # when a theme is used
    def test_with_theme_dark(self):
        self.spawn_server(theme='dark')
        
        res = self.post('/upload', files={
            'files': ('theme-dark-file', 'content-for-dark'),
        })
        self.assertEqual(res.status_code, 204)
        
        with open('theme-dark-file') as f: self.assertEqual(f.read(), 'content-for-dark')
    
    # There's no client-side testing to verify the theme or UI, but I can at least make sure the server runs
    # when a theme is used
    def test_with_theme_light(self):
        self.spawn_server(theme='light')
        
        res = self.post('/upload', files={
            'files': ('theme-light-file', 'content-for-light'),
        })
        self.assertEqual(res.status_code, 204)
        
        with open('theme-light-file') as f: self.assertEqual(f.read(), 'content-for-light')
    
    # Verify uploads are accepted when the token option is used and the correct token is supplied
    def test_token_valid_validate_endpoint(self):
        self.spawn_server(token='a-token')
        
        # 'files' option is used for both files and other form data
        res = self.post('/upload/validateToken', files={
            'token': (None, 'a-token'),
        })
        self.assertEqual(res.status_code, 204)
    
    # Verify uploads are accepted when the token option is used and the correct token is supplied
    def test_token_valid_upload_endpoint(self):
        self.spawn_server(token='a-token')
        
        # 'files' option is used for both files and other form data
        res = self.post('/upload', files={
            'files': ('valid-token-upload', 'token-upload-content'),
            'token': (None, 'a-token'),
        })
        self.assertEqual(res.status_code, 204)
        
        with open('valid-token-upload') as f: self.assertEqual(f.read(), 'token-upload-content')
    
    # Verify uploads are rejected when the token option is used and an incorrect token is supplied
    def test_token_invalid_validate_endpoint(self):
        self.spawn_server(token='a-token')
        
        # 'files' option is used for both files and other form data
        res = self.post('/upload/validateToken', files={
            'token': (None, 'a-bad-token'),
        })
        self.assertEqual(res.status_code, 403)
    
    # Verify uploads are rejected when the token option is used and an incorrect token is supplied
    def test_token_invalid_upload_endpoint(self):
        self.spawn_server(token='a-token')
        
        # 'files' option is used for both files and other form data
        res = self.post('/upload', files={
            'files': ('invalid-token-upload', 'token-upload-content'),
            'token': (None, 'a-bad-token'),
        })
        self.assertEqual(res.status_code, 403)
        
        self.assertFalse(Path('invalid-token-upload').exists())
    
    # Verify uploads are rejected when the token option is used and no token is supplied
    def test_token_missing_validate_endpoint(self):
        self.spawn_server(token='a-token')
        
        # 'files' option is used for both files and other form data
        res = self.post('/upload/validateToken', files={})
        self.assertEqual(res.status_code, 403)
    
    # Verify uploads are rejected when the token option is used and no token is supplied
    def test_token_missing_upload_endpoint(self):
        self.spawn_server(token='a-token')
        
        # 'files' option is used for both files and other form data
        res = self.post('/upload', files={
            'files': ('missing-token-upload', 'token-upload-content'),
        })
        self.assertEqual(res.status_code, 403)
        
        self.assertFalse(Path('missing-token-upload').exists())
    
    if PROTOCOL == 'HTTPS':
        def test_client_cert_valid(self):
            self.spawn_server(client_certificate=('../client.pem', '../client.crt'))
            
            res = self.post('/upload', cert='../client.pem', files={
                'files': ('valid-client-cert-upload', 'client-cert-upload-content'),
            })
            self.assertEqual(res.status_code, 204)
            
            with open('valid-client-cert-upload') as f: self.assertEqual(f.read(), 'client-cert-upload-content')
    
    if PROTOCOL == 'HTTPS':
        def test_client_cert_invalid(self):
            self.spawn_server(client_certificate=('../client.pem', '../client.crt'))
            
            self.assertRaises(requests.ConnectionError, lambda: self.post('/upload', cert='../server.pem', files={
                'files': ('invalid-client-cert-upload', 'client-cert-upload-content')
            }))
            
            self.assertFalse(Path('invalid-client-cert-upload').exists())
    
    if PROTOCOL == 'HTTPS':
        def test_client_cert_missing(self):
            self.spawn_server(client_certificate=('../client.pem', '../client.crt'))
            
            self.assertRaises(requests.ConnectionError, lambda: self.post('/upload', files={
                'files': ('missing-client-cert-upload', 'client-cert-upload-content'),
            }))
            
            self.assertFalse(Path('missing-client-cert-upload').exists())
    
    if PROTOCOL == 'HTTPS':
        # Verify that uploadserver will refuse to start if given a certificate inside its server root
        def test_certificate_not_allowed_in_root(self):
            shutil.copyfile('../server.pem', 'server.pem')
            
            result = subprocess.run(
                ['python', '-m', 'uploadserver', '-c', 'server.pem'],
                stdout=None if VERBOSE else subprocess.DEVNULL,
                stderr=None if VERBOSE else subprocess.DEVNULL,
            )
            
            self.assertEqual(result.returncode, 3)
    
    # Verify example curl command works
    def test_curl_example(self):
        self.spawn_server()
        
        result = subprocess.run([
                'curl', '-X', 'POST', '{}://localhost:8000/upload'.format(PROTOCOL.lower()),
                '--insecure', '-F', 'files=@../test-files/simple-example.txt',
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
                '--insecure', '-F', 'files=@../test-files/multiple-example-1.txt',
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
                '--insecure', '-F', 'files=@../test-files/token-example.txt', '-F', 'token=helloworld',
            ],
            stdout=None if VERBOSE else subprocess.DEVNULL,
            stderr=None if VERBOSE else subprocess.DEVNULL,
        )
        self.assertEqual(result.returncode, 0)
        
        with open('token-example.txt') as f_actual, open('../test-files/token-example.txt') as f_expected:
            self.assertEqual(f_actual.read(), f_expected.read())
    
    if PROTOCOL == 'HTTPS':
        # Verify example curl command with mTLS works
        def test_curl_mtls_example(self):
            self.spawn_server(client_certificate=('../client.pem', '../client.crt'))
            
            result = subprocess.run([
                    'curl', '-X', 'POST', '{}://localhost:8000/upload'.format(PROTOCOL.lower()),
                    '--insecure', '--cert', '../client.pem', '-F', 'files=@../test-files/mtls-example.txt',
                ],
                stdout=None if VERBOSE else subprocess.DEVNULL,
                stderr=None if VERBOSE else subprocess.DEVNULL,
            )
            self.assertEqual(result.returncode, 0)
            
            with open('mtls-example.txt') as f_actual, open('../test-files/mtls-example.txt') as f_expected:
                self.assertEqual(f_actual.read(), f_expected.read())
    
    def spawn_server(self, port=None, allow_replace=False, directory=None, theme=None, token=None,
        server_certificate=('../server.pem' if PROTOCOL == 'HTTPS' else None), client_certificate=None,
        basic_auth=None, basic_auth_upload=None
    ):
        args = ['python3', '-u', '-m', 'uploadserver']
        if port: args += [str(port)]
        if allow_replace: args += ['--allow-replace']
        if directory: args += ['-d', directory]
        if theme: args += ['--theme', theme]
        if token: args += ['-t', token]
        if server_certificate: args += ['-c', server_certificate]
        if client_certificate: args += ['--client-certificate', client_certificate[1]]
        if basic_auth:
            assert isinstance(basic_auth, HTTPBasicAuth)
            args += ['--basic-auth', f'{basic_auth.username}:{basic_auth.password}']
        if basic_auth_upload:
            assert isinstance(basic_auth_upload, HTTPBasicAuth)
            args += ['--basic-auth-upload', f'{basic_auth_upload.username}:{basic_auth_upload.password}']
        
        self.server = subprocess.Popen(args)
        
        # Wait for server to finish starting
        for _ in range(10):
            try:
                self.get('/', port=port or 8000,
                    cert=client_certificate[0] if client_certificate else None
                )
                break
            except requests.exceptions.ConnectionError:
                time.sleep(0.01)
        else:
            raise Exception('Port {} not responding. Did the server fail to start?'.format(port or 8000))
    
    def get(self, path, port=8000, *args, **kwargs):
        return requests.get('{}://127.0.0.1:{}{}'.format(PROTOCOL.lower(), port, path), verify=False, *args, **kwargs)
    
    def post(self, path, port=8000, *args, **kwargs):
        return requests.post('{}://127.0.0.1:{}{}'.format(PROTOCOL.lower(), port, path), verify=False, *args, **kwargs)
