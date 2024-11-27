import pytest, os, requests, subprocess, time, urllib3, shutil, sys
from pathlib import Path


assert 'VERBOSE' in os.environ, '$VERBOSE envionment variable not set'
VERBOSE = os.environ['VERBOSE']
assert VERBOSE in ['0', '1'], '$VERBOSE must be 0 or 1'
VERBOSE = int(VERBOSE)

assert 'PROTOCOL' in os.environ, '$PROTOCOL envionment variable not set'
PROTOCOL = os.environ['PROTOCOL']
assert PROTOCOL in ['HTTP', 'HTTPS'], 'Unknown $PROTOCOL: {}'.format(PROTOCOL)


TEST_BASIC_AUTH = requests.auth.HTTPBasicAuth('foo', 'bar')
TEST_BASIC_AUTH_BAD_USER = requests.auth.HTTPBasicAuth('foo2', 'bar')
TEST_BASIC_AUTH_BAD_PASS = requests.auth.HTTPBasicAuth('foo', 'bar2')
TEST_BASIC_AUTH_2 = requests.auth.HTTPBasicAuth('another user', 'pass')

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

# Verify a basic test can run. Most importantly, verify the sleep is long enough
# for the sever to start
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

def test_upload_put():
    spawn_server()
    
    res = put('/upload', files={
        'files': ('put-file', 'file-content'),
    })
    assert res.status_code == 204
    
    with open('put-file') as f: assert f.read() == 'file-content'

def test_basic_auth_get():
    spawn_server(basic_auth=TEST_BASIC_AUTH)
    
    assert get('/', auth=TEST_BASIC_AUTH).status_code == 200

def test_basic_auth_get_no_credentials():
    spawn_server(basic_auth=TEST_BASIC_AUTH)
    
    assert get('/').status_code == 401

def test_basic_auth_get_bad_user():
    spawn_server(basic_auth=TEST_BASIC_AUTH)
    
    assert get('/', auth=TEST_BASIC_AUTH_BAD_USER).status_code == 401

def test_basic_auth_get_bad_pass():
    spawn_server(basic_auth=TEST_BASIC_AUTH)
    
    assert get('/', auth=TEST_BASIC_AUTH_BAD_PASS).status_code == 401

def test_basic_auth_get_upload_only():
    spawn_server(basic_auth_upload=TEST_BASIC_AUTH)
    
    assert get('/').status_code == 200

@pytest.mark.parametrize('condition', ['basic_auth', 'basic_auth_upload'])
def test_basic_auth_post(condition):
    spawn_server(**{ condition: TEST_BASIC_AUTH })
    
    assert post('/upload', auth=TEST_BASIC_AUTH, files={
        'files': (condition, 'file-content'),
    }).status_code == 204
    
    with open(condition) as f: assert f.read() == 'file-content'

@pytest.mark.parametrize('condition', ['basic_auth', 'basic_auth_upload'])
def test_basic_auth_post_no_credentials(condition):
    spawn_server(**{ condition: TEST_BASIC_AUTH })
    
    assert post('/upload', files={
        'files': ('unauth-file', 'file-content'),
    }).status_code == 401
    
    assert not Path('unauth-file').exists()

@pytest.mark.parametrize('condition', ['basic_auth', 'basic_auth_upload'])
def test_basic_auth_post_bad_user(condition):
    spawn_server(**{ condition: TEST_BASIC_AUTH })
    
    assert post('/upload', auth=TEST_BASIC_AUTH_BAD_USER, files={
        'files': ('unauth-file', 'file-content'),
    }).status_code == 401
    
    assert not Path('unauth-file').exists()
    
@pytest.mark.parametrize('condition', ['basic_auth', 'basic_auth_upload'])
def test_basic_auth_post_bad_pass(condition):
    spawn_server(**{ condition: TEST_BASIC_AUTH })
    
    assert post('/upload', auth=TEST_BASIC_AUTH_BAD_PASS, files={
        'files': ('unauth-file', 'file-content'),
    }).status_code == 401
    
    assert not Path('unauth-file').exists()

def test_basic_auth_no_remnants():
    spawn_server(basic_auth=TEST_BASIC_AUTH)
    
    with open('../test-files/token-remnant-bug.txt') as f:
        # 'files' option is used for both files and other form data
        assert post('/upload', files={
            'files': ('token-remnant-bug.txt', f.read()),
        }).status_code == 401
    
    assert not Path('token-remnant-bug.txt').exists()
    
    # Check for bug #29, in which a blocked upload left behind tmp files.
    # Resolved by adding HTTP basic auth, which is not susceptible to this
    assert next(Path('.').glob('tmp*'), None) is None

@pytest.mark.parametrize('auth', [TEST_BASIC_AUTH, TEST_BASIC_AUTH_2])
def test_dual_basic_auth(auth):
    spawn_server(basic_auth=TEST_BASIC_AUTH,
        basic_auth_upload=TEST_BASIC_AUTH_2)
    
    res = get('/', auth=auth)
    assert res.status_code == 200

def test_dual_basic_auth_upload():
    spawn_server(basic_auth=TEST_BASIC_AUTH,
        basic_auth_upload=TEST_BASIC_AUTH_2)
    
    assert post('/upload', auth=TEST_BASIC_AUTH_2, files={
        'files': ('dual-auth', 'dual-auth-content'),
    }).status_code == 204
    
    with open('dual-auth') as f: assert f.read() == 'dual-auth-content'

def test_dual_basic_auth_upload_wrong_login():
    spawn_server(basic_auth=TEST_BASIC_AUTH,
        basic_auth_upload=TEST_BASIC_AUTH_2)
    
    assert post('/upload', auth=TEST_BASIC_AUTH, files={
        'files': ('unauth-file', 'file-content'),
    }).status_code == 401
    
    assert not Path('unauth-file').exists()

# Verify uploaded file is renamed if there is a collision
def test_upload_same_name_default():
    file_name = 'autorename'
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

# Uploads large enough to need a temp file have slightly different handling that
# needs to be tested
def test_large_upload():
    spawn_server()
    
    file_content = 1024*'a' + 1024*'b' + 1024*'c' + 1024*'d'
    
    res = post('/upload', files={
        'files': ('a-larger-file', file_content),
    })
    assert res.status_code == 204
    
    with open('a-larger-file') as f: assert f.read() == file_content

def test_url_encoded_file_name():
    spawn_server()
    
    file_content = 'A message from a strangely named file'
    
    res = post('/upload', files={
        'files': ('url%2Eencoding.txt', file_content)
    })
    assert res.status_code == 204
    
    with open('url%2Eencoding.txt') as f: assert f.read() == file_content

# Verify directory traversal attempts are contained within server folder
def test_directory_traversal():
    spawn_server()
    
    res = post('/upload', files={
        'files': ('../dt-name', 'dt-content'),
    })
    
    with open('dt-name') as f: assert f.read() == 'dt-content'
    assert not Path('../dt-name').exists()

def test_upload_respects_directory():
    spawn_server(directory='directory-option-test')
    
    res = post('/upload', files={
        'files': ('directory-file', 'file-content'),
    })
    assert res.status_code == 204
    
    with open('directory-option-test/directory-file') as f:
        assert f.read() == 'file-content'

# There's no client-side testing to verify the theme or UI, but I can at least
# make sure the server runs when a theme is used
def test_with_theme_dark():
    spawn_server(theme='dark')
    
    res = post('/upload', files={
        'files': ('theme-dark-file', 'content-for-dark'),
    })
    assert res.status_code == 204
    
    with open('theme-dark-file') as f: assert f.read() == 'content-for-dark'

# There's no client-side testing to verify the theme or UI, but I can at least
# make sure the server runs when a theme is used
def test_with_theme_light():
    spawn_server(theme='light')
    
    res = post('/upload', files={
        'files': ('theme-light-file', 'content-for-light'),
    })
    assert res.status_code == 204
    
    with open('theme-light-file') as f: assert f.read() == 'content-for-light'

def test_directory_listing_injections():
    spawn_server()
    
    res = get('/')
    assert res.status_code == 200
    assert int(res.headers['Content-Length']) == len(res.text)
    assert '<!-- Injected by uploadserver -->' in res.text
    assert '<a href="/upload">File upload</a>' in res.text

# Test this on the CGI variant too, to validate the funny inheritance pattern
def test_directory_listing_injections_cgi():
    spawn_server(cgi=True)
    
    res = get('/')
    assert res.status_code == 200
    assert int(res.headers['Content-Length']) == len(res.text)
    assert '<!-- Injected by uploadserver -->' in res.text
    assert '<a href="/upload">File upload</a>' in res.text

if PROTOCOL == 'HTTPS':
    def test_client_cert_valid():
        spawn_server(client_certificate=('../client.pem', '../client.crt'))
        
        res = post('/upload', cert='../client.pem', files={
            'files': ('valid-client-cert-upload', 'client-cert-upload-content'),
        })
        assert res.status_code == 204
        
        with open('valid-client-cert-upload') as f:
            assert f.read() == 'client-cert-upload-content'

if PROTOCOL == 'HTTPS':
    def test_client_cert_invalid():
        spawn_server(client_certificate=('../client.pem', '../client.crt'))
        
        with pytest.raises(requests.ConnectionError):
            post('/upload', cert='../server.pem', files={
                'files': ('invalid-client-cert-upload',
                    'client-cert-upload-content')
            })
        
        assert not Path('invalid-client-cert-upload').exists()

if PROTOCOL == 'HTTPS':
    def test_client_cert_missing():
        spawn_server(client_certificate=('../client.pem', '../client.crt'))
        
        with pytest.raises(requests.ConnectionError):
            post('/upload', files={
                'files': ('missing-client-cert-upload',
                    'client-cert-upload-content'),
            })
        
        assert not Path('missing-client-cert-upload').exists()

if PROTOCOL == 'HTTPS':
    # Verify that uploadserver will refuse to start if given a certificate
    # inside its server root
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
            'curl', '-X', 'POST', f'{PROTOCOL.lower()}://localhost:8000/upload',
            '--insecure', '-F', 'files=@../test-files/simple-example.txt',
        ],
        stdout=None if VERBOSE else subprocess.DEVNULL,
        stderr=None if VERBOSE else subprocess.DEVNULL,
    )
    
    assert result.returncode == 0
    
    with open('simple-example.txt') as f_actual:
        with open('../test-files/simple-example.txt') as f_expected:
            assert f_actual.read() == f_expected.read()

# Verify example curl command with multiple files works
def test_curl_multiple_example():
    spawn_server()
    
    result = subprocess.run([
            'curl', '-X', 'POST', f'{PROTOCOL.lower()}://localhost:8000/upload',
            '--insecure', '-F', 'files=@../test-files/multiple-example-1.txt',
            '-F', 'files=@../test-files/multiple-example-2.txt',
        ],
        stdout=None if VERBOSE else subprocess.DEVNULL,
        stderr=None if VERBOSE else subprocess.DEVNULL,
    )
    
    assert result.returncode == 0
    
    with open('multiple-example-1.txt') as f_actual:
        with open('../test-files/multiple-example-1.txt') as f_expected:
            assert f_actual.read() == f_expected.read()
    with open('multiple-example-2.txt') as f_actual:
        with open('../test-files/multiple-example-2.txt') as f_expected:
            assert f_actual.read() == f_expected.read()

if PROTOCOL == 'HTTPS':
    # Verify example curl command with mTLS works
    def test_curl_mtls_example():
        spawn_server(client_certificate=('../client.pem', '../client.crt'))
        
        result = subprocess.run([
                'curl', '-X', 'POST',
                f'{PROTOCOL.lower()}://localhost:8000/upload',
                '--insecure', '--cert', '../client.pem', '-F',
                'files=@../test-files/mtls-example.txt',
            ],
            stdout=None if VERBOSE else subprocess.DEVNULL,
            stderr=None if VERBOSE else subprocess.DEVNULL,
        )
        assert result.returncode == 0
        
        with open('mtls-example.txt') as f_actual:
            with open('../test-files/mtls-example.txt') as f_expected:
                assert f_actual.read() == f_expected.read()

# Verify example curl command with HTTP basic auth works
def test_http_basic_auth_example():
    spawn_server(basic_auth=requests.auth.HTTPBasicAuth('hello', 'world'))
    
    result = subprocess.run([
            'curl', '-X', 'POST', f'{PROTOCOL.lower()}://localhost:8000/upload',
            '--insecure', '-F', 'files=@../test-files/basic-auth-example.txt',
            '-u', 'hello:world',
        ],
        stdout=None if VERBOSE else subprocess.DEVNULL,
        stderr=None if VERBOSE else subprocess.DEVNULL,
    )
    assert result.returncode == 0
    
    with open('basic-auth-example.txt') as f_actual:
        with open('../test-files/basic-auth-example.txt') as f_expected:
            assert f_actual.read() == f_expected.read()

# Make sure --help output in readme is updated. Use Python 3.13 for help output
# (since its generated by argparse and sometimes changes between versions)
if sys.version_info.major == 3 and sys.version_info.minor == 13:
    def test_help_info_in_readme():
        result = subprocess.run([
                sys.executable, '-u', '-m', 'uploadserver', '-h',
            ],
            capture_output=True,
            env={ 'COLUMNS': '80' },
        )
        assert result.returncode == 0
        
        print(result.stdout)
        
        with open('../README.md', 'rb') as f:
            assert result.stdout in f.read(), '--help output not found in ' + \
                'README.md, does the readme need to be updated?'

###########
# Helpers #
###########

# Cannot be made into a fixture because fixture do not allow passing arguments
# in Python 3.6 (so I could make it into a fixture now that 3.6 is long
# dropped...). All of these arguments (except for the bool ones) are really
# some_type | None, but Python 3.9 doesn't support |
def spawn_server(
    port: int = None,
    cgi: bool = False,
    allow_replace: bool = False,
    directory: str = None,
    theme: str = None,
    server_certificate: str = ('../server.pem' if PROTOCOL == 'HTTPS'
        else None),
    client_certificate: str = None,
    basic_auth: requests.auth.HTTPBasicAuth = None,
    basic_auth_upload: requests.auth.HTTPBasicAuth = None,
):
    args = [sys.executable, '-u', '-m', 'uploadserver']
    if port: args += [str(port)]
    if cgi: args += ['--cgi']
    if allow_replace: args += ['--allow-replace']
    if directory: args += ['-d', directory]
    if theme: args += ['--theme', theme]
    if server_certificate: args += ['-c', server_certificate]
    if client_certificate: args += ['--client-certificate',
        client_certificate[1]]
    if basic_auth:
        args += ['--basic-auth', f'{basic_auth.username}:{basic_auth.password}']
    if basic_auth_upload:
        args += ['--basic-auth-upload',
            f'{basic_auth_upload.username}:{basic_auth_upload.password}']
    
    server_holder[0] = subprocess.Popen(args)
    
    # Wait for server to finish starting
    for _ in range(100):
        try:
            get('/', port=port or 8000,
                cert=client_certificate[0] if client_certificate else None
            )
            break
        except requests.exceptions.ConnectionError:
            time.sleep(0.01)
    else:
        raise Exception(f'Port {port or 8000} not responding. Did the server '
            'fail to start?')

def get(path: str, port: int = 8000, *args, **kwargs) -> requests.Response:
    return requests.get(f'{PROTOCOL.lower()}://127.0.0.1:{port}{path}',
        verify=False, *args, **kwargs)

def post(path: str, port: int = 8000, *args, **kwargs) -> requests.Response:
    return requests.post(f'{PROTOCOL.lower()}://127.0.0.1:{port}{path}',
        verify=False, *args, **kwargs)

def put(path: str, port: int = 8000, *args, **kwargs) -> requests.Response:
    return requests.put(f'{PROTOCOL.lower()}://127.0.0.1:{port}{path}',
        verify=False, *args, **kwargs)
