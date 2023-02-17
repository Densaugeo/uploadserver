#!/bin/bash
set -euf -o pipefail

make test PY=python3.6 VERBOSE=0
make test PY=python3.6 VERBOSE=0 PROTOCOL=HTTPS
make test PY=python3.7 VERBOSE=0
make test PY=python3.7 VERBOSE=0 PROTOCOL=HTTPS
make test PY=python3.8 VERBOSE=0
make test PY=python3.8 VERBOSE=0 PROTOCOL=HTTPS
make test PY=python3.9 VERBOSE=0
make test PY=python3.9 VERBOSE=0 PROTOCOL=HTTPS
make test PY=python3.10 VERBOSE=0
make test PY=python3.10 VERBOSE=0 PROTOCOL=HTTPS
make test PY=python3.11 VERBOSE=0
make test PY=python3.11 VERBOSE=0 PROTOCOL=HTTPS
make test PY=python3.12 VERBOSE=0
make test PY=python3.12 VERBOSE=0 PROTOCOL=HTTPS
