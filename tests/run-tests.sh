#!/bin/bash

# Python versions to use for tests
pyenv_versions="3.12.2 3.11.9 3.10.14 3.9.19 3.8.19"

# Ensure pyenv is available and initialised
eval "$(pyenv init -)"

Usage() {
    echo "Usage: $0 [--install-versions] [--init]"
    echo "  --install-pyversions: Install the Python versions"
    echo "  --init-pyversions: Setup the Python versions"
    echo "  --pyversion <version|all>: Run tests for specific Python versions"
    echo "  --firmware <file|all>: Run tests for specific firmware files"
    echo "  --device <device>: Run tests for device on serial port"
    exit 1
}

testdir=$(dirname $0)

args=""
while [ $# -gt 0 ]; do
    case $1 in
        --install-pyversions)
            # Install the Python versions
            for version in $pyenv_versions; do
                pyenv install -s $version
            done
            ;;
        --init-pyversions)
            # Setup the Python versions
            for version in $pyenv_versions; do
                pyenv shell $version
                pyenv exec pip install --upgrade pip
                pyenv exec pip install pytest
                pyenv exec pip install -r requirements.txt
            done
            ;;
        --pyversion)
            # Run the tests for the specified Python versions
            if [ "$2" = "all" ]; then
                versions="$pyenv_versions"
            else
                versions="$2"
            fi
            shift
            ;;
        --firmware)
            # Run the tests on the specified firmware
            if [ "$2" = "all" ]; then
                files="$(ls ${testdir}/data/ESP*.bin)"
            else
                files="$(ls ${testdir}/data/*$2*)"
            fi
            shift
            ;;
        --device)
            # Run the tests on the specified device
            args="$args --device $2"
            shift
            ;;
        *)
            args="$args $arg"
            ;;
    esac
    shift
done

# Run the tests
if [ -n "$versions" ]; then
    echo "Running tests for Python versions: $versions"
    for version in $versions; do
        echo "Running tests for Python $version"
        pyenv shell $version
        pyenv exec python -m pytest $args
    done
    exit 0
fi

if [ -n "$files" ]; then
    echo "Running tests for firmware files: $files"
    for f in $files; do
        name=$(basename $f)
        echo "Running tests for firmware file: $name"
        pytest $args --firmware $name
    done
    exit 0
fi

pytest $args

