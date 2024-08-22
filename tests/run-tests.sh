#!/bin/bash

# Python versions to use for tests
pyenv_versions="3.12.2 3.11.9 3.10.14 3.9.19 3.8.19"

# Ensure pyenv is available and initialised
eval "$(pyenv init -)"

Usage() {
    echo "Usage: $0 [--install-versions] [--init]"
    echo "  --install-versions: Install the Python versions"
    echo "  --init: Setup the Python versions"
    exit 1
}

for arg in $@; do
    case $arg in
        --install-versions)
            # Install the Python versions
            for version in $pyenv_versions; do
                pyenv install -s $version
            done
            ;;
        --init-versions)
            # Setup the Python versions
            for version in $pyenv_versions; do
                pyenv shell $version
                pyenv exec pip install --upgrade pip
                pyenv exec pip install pytest
                pyenv exec pip install -r requirements.txt
            done
            ;;
        --versions)
            # Run the tests for the specified Python versions
            versions="$pyenv_versions"
            ;;
        -v)
            # List the Python versions
            versions="$versions $2"
            shift
            ;;
        --device)
            # Run the tests on the specified device
            device="$2"
            shift
            ;;
        *)
            echo "Unknown argument: $arg"
            exit 1
            ;;
    esac
done

# Run the tests
if [ -n "$versions" ]; then
    echo "Running tests for Python versions: $versions"
    for version in $versions; do
        echo "Running tests for Python $version"
        pyenv shell $version
        pyenv exec python -m pytest
    done
fi

if [ -n "$device" ]; then
    echo "Running tests on device: $device"
    pyenv exec python -m pytest --device $device
fi


