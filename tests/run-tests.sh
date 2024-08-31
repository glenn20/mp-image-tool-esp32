#!/bin/bash

# Uses 'uv' to run tests for multiple Python versions
# and/or firmware files. The 'uv' command can be installed
# using pip, eg:
#
#  pip install --user uv

# Python versions to use for tests
pyversions="3.12 3.11 3.10 3.9 3.8"

Usage() {
    echo "Usage: $0 [--install-versions] [--init]"
    echo "  --firmware <file|all>: Run tests for specific firmware files"
    echo "  --port <device>: Run tests for device on serial port"
    exit 1
}

if ! type -P uv >/dev/null; then
    echo "uv is not installed"
    echo "Please install uv using 'pip install --user uv'"
    exit 1
fi

testdir=$(dirname $0)

args=""
versions=""
files=""
while [ $# -gt 0 ]; do
    case $1 in
        --version|-v)
            # Run the tests for the specified Python versions
            if [ "$2" = "all" ]; then
                versions="$pyversions"
            else
                versions="$2"
            fi
            shift
            ;;
        --firmware|-f)
            # Run the tests on the specified firmware
            if [ "$2" = "all" ]; then
                files="$(ls ${testdir}/data/ESP*.bin)"
            else
                files="$(ls ${testdir}/data/*$2*)"
            fi
            shift
            ;;
        --port|-p)
            # Run the tests on the specified device
            args="$args --port $2"
            shift
            ;;
        *)
            args="$args $1"
            if [ "$1" = "-x" ]; then
                set -o errexit -o pipefail -o noclobber -o nounset
            fi
            ;;
    esac
    shift
done

# Run the tests
if [ -n "$versions" ]; then
    echo "Running tests for Python versions: $versions"
    for version in $versions; do
        echo "Running tests for Python $version"
        uv run --python $version pytest $args
    done
    exit 0
fi

if [ -n "$files" ]; then
    echo "Running tests for firmware files: $files"
    for f in $files; do
        name=$(basename $f)
        echo "Running tests for firmware file: $name"
        uv run pytest $args --firmware $name
    done
    exit 0
fi

uv run pytest $args

