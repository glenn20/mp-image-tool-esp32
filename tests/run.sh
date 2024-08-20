#!/bin/bash

# Python versions to use for tests
versions="3.12.2 3.11.9 3.10.14 3.9.19 3.8.19"

# Ensure pyenv is available and initialised
eval "$(pyenv init -)"

for arg in $@; do
    case $arg in
        --install)
            # Install the Python versions
            for version in $versions; do
                pyenv install -s $version
            done
            ;;
        --init)
            # Setup the Python versions
            for version in $versions; do
                pyenv shell $version
                pyenv exec pip install --upgrade pip
                pyenv exec pip install pytest
                pyenv exec pip install -r requirements.txt
            done
            ;;
        *)
            echo "Unknown argument: $arg"
            exit 1
            ;;
    esac
done

# Run the tests
for version in $versions; do
    echo "Running tests for Python $version"
    pyenv shell $version
    pyenv exec python -m pytest
done
