import pytest, os, requests, subprocess, time, urllib3, shutil, sys
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


server_holder = [None]

####################
# Setup / Teardown #
####################

def setup_module():
    os.mkdir(Path(__file__).parent / 'test-temp')
    os.chdir(Path(__file__).parent / 'test-temp')
    os.symlink('../uploadserver', 'uploadserver')
    os.mkdir('directory-option-test')

def setup_function():
    print()
    urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

def teardown_function():
    if server_holder[0]: server_holder[0].terminate()

#########
# Tests #
#########

# Verify a basic test can run. Most importantly, verify the sleep is long enough for the sever to start
def test_basic():
    spawn_server()
    
    res = get('/')
    assert res.status_code == 200

# Verify the --port argument is properly passed to the underlying http.server
def test_argument_passthrough():
    spawn_server(port=8080)
    
    res = get('/', port=8080)
    assert res.status_code == 200
    with pytest.raises(requests.ConnectionError): get('/')

# Verify /upload at least responds to GET
def test_upload_page_exists():
    spawn_server()
    
    res = get('/upload')
    assert res.status_code == 200

# Simple upload test
def test_upload():
    spawn_server()
    
    res = post('/upload', files={
        'files': ('a-file', 'file-content'),
    })
    assert res.status_code == 204
    
    with open('a-file') as f: assert f.read() == 'file-content'

# Basic auth on everything
def test_basic_auth():
    spawn_server(basic_auth=TEST_BASIC_AUTH)
    
    # auth GET / - succeeds
    res = get('/', auth=TEST_BASIC_AUTH)
    assert res.status_code == 200
    
    # unauth GET / - fails
    res = get('/')
    assert res.status_code == 401
    
    # baduser auth GET / - fails
    res = get('/', auth=TEST_BASIC_AUTH_BAD_USER)
    assert res.status_code == 401
    
    # badpass auth GET / - fails
    res = get('/', auth=TEST_BASIC_AUTH_BAD_PASS)
    assert res.status_code == 401
    
    _test_basic_auth_upload()

# Basic auth on upload only
def test_basic_auth_upload():
    spawn_server(basic_auth_upload=TEST_BASIC_AUTH)
    
    # unauth GET / - succeeds
    res = get('/')
    assert res.status_code == 200
    
    _test_basic_auth_upload()

def _test_basic_auth_upload():
    # auth POST /upload - succeeds
    res = post('/upload', auth=TEST_BASIC_AUTH, files={
        'files': ('a-file', 'file-content'),
    })
    assert res.status_code == 204
    with open('a-file') as f: assert f.read() == 'file-content'
    
    # unauth POST /upload - fails
    res = post('/upload', files={
        'files': ('a-file', 'file-content'),
    })
    assert res.status_code == 401
    
    # baduser POST /upload - fails
    res = post('/upload', auth=TEST_BASIC_AUTH_BAD_USER, files={
        'files': ('a-file', 'file-content'),
    })
    assert res.status_code == 401
    
    # badpass POST /upload - fails
    res = post('/upload', auth=TEST_BASIC_AUTH_BAD_PASS, files={
        'files': ('a-file', 'file-content'),
    })
    assert res.status_code == 401

# Verify uploaded file is renamed if there is a collision
def test_upload_same_name_default():
    file_name = 'b-file'
    file_renamed = f'{file_name} (1)'  # this is the auto-renaming pattern
    
    spawn_server()
    
    res = post('/upload', files={
        'files': (file_name, 'file-content'),
    })
    assert res.status_code == 204
    res = post('/upload', files={
        'files': (file_name, 'file-content-same-name'),
    })
    assert res.status_code == 204
    
    with open(file_name) as f: assert f.read() == 'file-content'
    with open(file_renamed) as f: assert f.read() == 'file-content-same-name'

# Verify uploads replace existing file with the same name
def test_upload_same_name_replace():
    file_name = 'c-file'
    file_renamed = f'{file_name} (1)'  # this is the auto-renaming pattern
    
    spawn_server(allow_replace=True)
    
    res = post('/upload', files={
        'files': (file_name, 'file-content'),
    })
    assert res.status_code == 204
    res = post('/upload', files={
        'files': (file_name, 'file-content-replaced'),
    })
    assert res.status_code == 204
    
    with open(file_name) as f: assert f.read() == 'file-content-replaced'
    assert os.path.isfile(file_renamed) == False

def test_upload_bad_path():
    spawn_server()
    
    res = post('/uploadx', files={
        'file_foo': ('a-file', 'file-content'),
    })
    assert res.status_code == 404

# Test a malformed upload
def test_upload_bad_field_name():
    spawn_server()
    
    res = post('/upload', files={
        'file_foo': ('a-file', 'file-content'),
    })
    assert res.status_code == 400

def test_upload_no_files():
    spawn_server()
    
    res = post('/upload', files={
        'files': ('', ''),
    })
    assert res.status_code == 400

# Verify multiple file upload works
def test_multiple_upload():
    spawn_server()
    
    res = post('/upload', files=[
        ('files', ('file-1', 'file-content-1')),
        ('files', ('file-2', 'file-content-2')),
    ])
    assert res.status_code == 204
    
    with open('file-1') as f: assert f.read() == 'file-content-1'
    with open('file-2') as f: assert f.read() == 'file-content-2'

# Uploads large enough to need a temp file have slightly different handling that needs to be tested
def test_large_upload():
    spawn_server()
    
    file_content = 1024*'a' + 1024*'b' + 1024*'c' + 1024*'d'
    
    res = post('/upload', files={
        'files': ('a-larger-file', file_content),
    })
    assert res.status_code == 204
    
    with open('a-larger-file') as f: assert f.read() == file_content

# Verify directory traversal attempts are contained within server folder
def test_directory_traversal():
    spawn_server()
    
    res = post('/upload', files={
        'files': ('../dt-name', 'dt-content'),
    })
    
    with open('dt-name') as f: assert f.read() == 'dt-content'
    assert not Path('../dt-name').exists()

# Directory option was added to http.server in Python 3.7
if sys.version_info.major >= 3 and sys.version_info.minor >= 7:
    def test_upload_respects_directory():
        spawn_server(directory='directory-option-test')
        
        res = post('/upload', files={
            'files': ('directory-file', 'file-content'),
        })
        assert res.status_code == 204
        
        with open('directory-option-test/directory-file') as f: assert f.read() == 'file-content'

# There's no client-side testing to verify the theme or UI, but I can at least make sure the server runs
# when a theme is used
def test_with_theme_dark():
    spawn_server(theme='dark')
    
    res = post('/upload', files={
        'files': ('theme-dark-file', 'content-for-dark'),
    })
    assert res.status_code == 204
    
    with open('theme-dark-file') as f: assert f.read() == 'content-for-dark'

# There's no client-side testing to verify the theme or UI, but I can at least make sure the server runs
# when a theme is used
def test_with_theme_light():
    spawn_server(theme='light')
    
    res = post('/upload', files={
        'files': ('theme-light-file', 'content-for-light'),
    })
    assert res.status_code == 204
    
    with open('theme-light-file') as f: assert f.read() == 'content-for-light'

# Verify uploads are accepted when the token option is used and the correct token is supplied
def test_token_valid_validate_endpoint():
    spawn_server(token='a-token')
    
    # 'files' option is used for both files and other form data
    res = post('/upload/validateToken', files={
        'token': (None, 'a-token'),
    })
    assert res.status_code == 204

# Verify uploads are accepted when the token option is used and the correct token is supplied
def test_token_valid_upload_endpoint():
    spawn_server(token='a-token')
    
    # 'files' option is used for both files and other form data
    res = post('/upload', files={
        'files': ('valid-token-upload', 'token-upload-content'),
        'token': (None, 'a-token'),
    })
    assert res.status_code == 204
    
    with open('valid-token-upload') as f: assert f.read() == 'token-upload-content'

# Verify uploads are rejected when the token option is used and an incorrect token is supplied
def test_token_invalid_validate_endpoint():
    spawn_server(token='a-token')
    
    # 'files' option is used for both files and other form data
    res = post('/upload/validateToken', files={
        'token': (None, 'a-bad-token'),
    })
    assert res.status_code == 403

# Verify uploads are rejected when the token option is used and an incorrect token is supplied
def test_token_invalid_upload_endpoint():
    spawn_server(token='a-token')
    
    # 'files' option is used for both files and other form data
    res = post('/upload', files={
        'files': ('invalid-token-upload', 'token-upload-content'),
        'token': (None, 'a-bad-token'),
    })
    assert res.status_code == 403
    
    assert not Path('invalid-token-upload').exists()

# Verify uploads are rejected when the token option is used and no token is supplied
def test_token_missing_validate_endpoint():
    spawn_server(token='a-token')
    
    # 'files' option is used for both files and other form data
    res = post('/upload/validateToken', files={})
    assert res.status_code == 403

# Verify uploads are rejected when the token option is used and no token is supplied
def test_token_missing_upload_endpoint():
    spawn_server(token='a-token')
    
    # 'files' option is used for both files and other form data
    res = post('/upload', files={
        'files': ('missing-token-upload', 'token-upload-content'),
    })
    assert res.status_code == 403
    
    assert not Path('missing-token-upload').exists()

if PROTOCOL == 'HTTPS':
    def test_client_cert_valid():
        spawn_server(client_certificate=('../client.pem', '../client.crt'))
        
        res = post('/upload', cert='../client.pem', files={
            'files': ('valid-client-cert-upload', 'client-cert-upload-content'),
        })
        assert res.status_code == 204
        
        with open('valid-client-cert-upload') as f: assert f.read() == 'client-cert-upload-content'

if PROTOCOL == 'HTTPS':
    def test_client_cert_invalid():
        spawn_server(client_certificate=('../client.pem', '../client.crt'))
        
        with pytest.raises(requests.ConnectionError): post('/upload', cert='../server.pem', files={
            'files': ('invalid-client-cert-upload', 'client-cert-upload-content')
        })
        
        assert not Path('invalid-client-cert-upload').exists()

if PROTOCOL == 'HTTPS':
    def test_client_cert_missing():
        spawn_server(client_certificate=('../client.pem', '../client.crt'))
        
        with pytest.raises(requests.ConnectionError): post('/upload', files={
            'files': ('missing-client-cert-upload', 'client-cert-upload-content'),
        })
        
        assert not Path('missing-client-cert-upload').exists()

if PROTOCOL == 'HTTPS':
    # Verify that uploadserver will refuse to start if given a certificate inside its server root
    def test_certificate_not_allowed_in_root():
        shutil.copyfile('../server.pem', 'server.pem')
        
        result = subprocess.run(
            ['python', '-m', 'uploadserver', '-c', 'server.pem'],
            stdout=None if VERBOSE else subprocess.DEVNULL,
            stderr=None if VERBOSE else subprocess.DEVNULL,
        )
        
        assert result.returncode == 3

# Verify example curl command works
def test_curl_example():
    spawn_server()
    
    result = subprocess.run([
            'curl', '-X', 'POST', '{}://localhost:8000/upload'.format(PROTOCOL.lower()),
            '--insecure', '-F', 'files=@../test-files/simple-example.txt',
        ],
        stdout=None if VERBOSE else subprocess.DEVNULL,
        stderr=None if VERBOSE else subprocess.DEVNULL,
    )
    
    assert result.returncode == 0
    
    with open('simple-example.txt') as f_actual, open('../test-files/simple-example.txt') as f_expected:
        assert f_actual.read() == f_expected.read()

# Verify example curl command with multiple files works
def test_curl_multiple_example():
    spawn_server()
    
    result = subprocess.run([
            'curl', '-X', 'POST', '{}://localhost:8000/upload'.format(PROTOCOL.lower()),
            '--insecure', '-F', 'files=@../test-files/multiple-example-1.txt',
            '-F', 'files=@../test-files/multiple-example-2.txt',
        ],
        stdout=None if VERBOSE else subprocess.DEVNULL,
        stderr=None if VERBOSE else subprocess.DEVNULL,
    )
    
    assert result.returncode == 0
    
    with open('multiple-example-1.txt') as f_actual, open('../test-files/multiple-example-1.txt') as f_expected:
        assert f_actual.read() == f_expected.read()
    with open('multiple-example-2.txt') as f_actual, open('../test-files/multiple-example-2.txt') as f_expected:
        assert f_actual.read() == f_expected.read()

# Verify example curl command with token works
def test_curl_token_example():
    spawn_server(token='helloworld')
    
    result = subprocess.run([
            'curl', '-X', 'POST', '{}://localhost:8000/upload'.format(PROTOCOL.lower()),
            '--insecure', '-F', 'files=@../test-files/token-example.txt', '-F', 'token=helloworld',
        ],
        stdout=None if VERBOSE else subprocess.DEVNULL,
        stderr=None if VERBOSE else subprocess.DEVNULL,
    )
    assert result.returncode == 0
    
    with open('token-example.txt') as f_actual, open('../test-files/token-example.txt') as f_expected:
        assert f_actual.read() == f_expected.read()

if PROTOCOL == 'HTTPS':
    # Verify example curl command with mTLS works
    def test_curl_mtls_example():
        spawn_server(client_certificate=('../client.pem', '../client.crt'))
        
        result = subprocess.run([
                'curl', '-X', 'POST', '{}://localhost:8000/upload'.format(PROTOCOL.lower()),
                '--insecure', '--cert', '../client.pem', '-F', 'files=@../test-files/mtls-example.txt',
            ],
            stdout=None if VERBOSE else subprocess.DEVNULL,
            stderr=None if VERBOSE else subprocess.DEVNULL,
        )
        assert result.returncode == 0
        
        with open('mtls-example.txt') as f_actual, open('../test-files/mtls-example.txt') as f_expected:
            assert f_actual.read() == f_expected.read()

###########
# Helpers #
###########

# Cannot be made into a fixture because fixture do not allow passing arguments in Python 3.6
def spawn_server(port=None, allow_replace=False, directory=None, theme=None, token=None,
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
    
    server_holder[0] = subprocess.Popen(args)
    
    # Wait for server to finish starting
    for _ in range(10):
        try:
            get('/', port=port or 8000,
                cert=client_certificate[0] if client_certificate else None
            )
            break
        except requests.exceptions.ConnectionError:
            time.sleep(0.01)
    else:
        raise Exception('Port {} not responding. Did the server fail to start?'.format(port or 8000))

def get(path, port=8000, *args, **kwargs):
    return requests.get('{}://127.0.0.1:{}{}'.format(PROTOCOL.lower(), port, path), 
        verify=False, *args, **kwargs)

def post(path, port=8000, *args, **kwargs):
    return requests.post('{}://127.0.0.1:{}{}'.format(PROTOCOL.lower(), port, path), 
        verify=False, *args, **kwargs)
