#!/bin/bash
set -euf -o pipefail

make test PY=python3.6
make test PY=python3.6 PROTOCOL=HTTPS
make test PY=python3.7
make test PY=python3.7 PROTOCOL=HTTPS
make test PY=python3.8
make test PY=python3.8 PROTOCOL=HTTPS
make test PY=python3.9
make test PY=python3.9 PROTOCOL=HTTPS
